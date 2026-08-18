from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from math import ceil

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (QColor, QContextMenuEvent, QFont, QFontDatabase, QFontMetricsF,
                          QKeyEvent, QKeySequence, QMouseEvent, QPainter, QPalette)
from PySide6.QtWidgets import QAbstractScrollArea, QApplication, QMenu


@dataclass(slots=True)
class HexSelection:
    anchor: int | None = None
    cursor: int | None = None

    @property
    def bounds(self) -> tuple[int, int] | None:
        if self.anchor is None or self.cursor is None:
            return None
        return min(self.anchor, self.cursor), max(self.anchor, self.cursor)


@dataclass(frozen=True, slots=True)
class HexGridGeometry:
    offset_rect: QRect
    hex_rect: QRect
    ascii_rect: QRect
    hex_cells: tuple[QRect, ...]
    ascii_cells: tuple[QRect, ...]
    minimum_width: int

    def __post_init__(self) -> None:
        assert self.offset_rect.right() < self.hex_rect.left()
        assert self.hex_rect.right() < self.ascii_rect.left()
        assert len(self.hex_cells) == len(self.ascii_cells) == 16
        assert self.hex_cells[0].left() >= self.hex_rect.left()
        assert self.hex_cells[-1].right() <= self.hex_rect.right()
        assert self.ascii_cells[0].left() >= self.ascii_rect.left()
        assert self.ascii_cells[-1].right() <= self.ascii_rect.right()


class HexGridWidget(QAbstractScrollArea):
    """Read-only, painted and virtualized hexadecimal grid."""

    window_requested = Signal(int, int, int)
    selection_changed = Signal(object, object)
    cursor_changed = Signal(int, object)
    copy_hex_requested = Signal()
    copy_ascii_requested = Signal()
    detect_requested = Signal()
    hash_requested = Signal()
    extract_requested = Signal()

    BYTES_PER_LINE = 16
    HEADER_HEIGHT = 26
    WINDOW_BYTES = 64 * 1024
    CACHE_WINDOWS = 6
    SCROLL_STEPS = 1_000_000
    OUTER_MARGIN = 6
    OFFSET_HEX_GAP = 10
    HEX_ASCII_GAP = 14
    OFFSET_PADDING = 10
    ASCII_PADDING = 6

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HexGrid")
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        palette = self.palette()
        palette.setColor(QPalette.Base, QColor("#0b1119"))
        palette.setColor(QPalette.AlternateBase, QColor("#111a24"))
        palette.setColor(QPalette.Text, QColor("#d8e2ec"))
        palette.setColor(QPalette.PlaceholderText, QColor("#8290a0"))
        palette.setColor(QPalette.Mid, QColor("#263442"))
        self.setPalette(palette)
        self._font = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        self._font.setPointSize(9)
        self._metrics = QFontMetricsF(self._font)
        self._row_height = max(22, ceil(self._metrics.height()) + 7)
        self._file_size = 0
        self._first_line = 0
        self._cursor: int | None = None
        self._selection = HexSelection()
        self._dragging = False
        self._cache: OrderedDict[int, bytes] = OrderedDict()
        self._request_serial = 0
        self._pending_pages: set[int] = set()
        self._loading = False
        self._error = ""
        self._hover_offset: int | None = None
        self.verticalScrollBar().valueChanged.connect(self._scroll_changed)
        self.horizontalScrollBar().valueChanged.connect(lambda _value: self.viewport().update())

    @property
    def file_size(self) -> int:
        return self._file_size

    @property
    def current_offset(self) -> int | None:
        return self._cursor

    @property
    def selection_start(self) -> int | None:
        bounds = self._selection.bounds
        return bounds[0] if bounds else None

    @property
    def selection_end(self) -> int | None:
        bounds = self._selection.bounds
        return bounds[1] if bounds else None

    @property
    def selection_length(self) -> int:
        bounds = self._selection.bounds
        return 0 if bounds is None else bounds[1] - bounds[0] + 1

    @property
    def loaded_bytes(self) -> int:
        return sum(len(value) for value in self._cache.values())

    @property
    def cached_window_count(self) -> int:
        return len(self._cache)

    @property
    def visible_row_capacity(self) -> int:
        return max(1, (self.viewport().height() - self.HEADER_HEIGHT) // self._row_height)

    def set_file(self, file_size: int) -> None:
        self._file_size = max(0, int(file_size))
        self._first_line = 0
        self._cursor = None
        self._selection = HexSelection()
        self._cache.clear()
        self._pending_pages.clear()
        self._loading = False
        self._error = ""
        self._configure_scrollbar()
        self._configure_horizontal_scrollbar()
        self.viewport().update()
        self.selection_changed.emit(None, None)
        if self._file_size:
            self._ensure_window(0)

    def clear(self) -> None:
        self.set_file(0)

    def set_grid_font(self, font: QFont) -> None:
        """Apply display font and recompute geometry from its real metrics."""
        self._font = QFont(font)
        self._metrics = QFontMetricsF(self._font)
        self._row_height = max(22, ceil(self._metrics.height()) + 7)
        self._configure_scrollbar()
        self._configure_horizontal_scrollbar()
        self.viewport().update()

    def set_loading(self) -> None:
        self._loading = True
        self.viewport().update()

    def set_error(self, category: str, message: str) -> None:
        self._loading = False
        self._error = f"{category} · {message}"
        self.viewport().update()

    def accept_window(self, offset: int, payload: bytes | bytearray | memoryview,
                      request_id: int | None = None) -> None:
        page = self._page_start(offset)
        self._pending_pages.discard(page)
        self._cache[page] = bytes(payload)
        self._cache.move_to_end(page)
        while len(self._cache) > self.CACHE_WINDOWS:
            self._cache.popitem(last=False)
        self._loading = bool(self._pending_pages)
        self._error = ""
        self.viewport().update()
        if self._cursor is not None:
            self._emit_cursor()

    def byte_at(self, offset: int) -> int | None:
        if not 0 <= offset < self._file_size:
            return None
        page = self._page_start(offset)
        payload = self._cache.get(page)
        if payload is None:
            return None
        index = offset - page
        return payload[index] if index < len(payload) else None

    def set_selection(self, start: int | None, end: int | None, *, navigate: bool = False) -> None:
        if start is None or end is None or not self._file_size:
            self._selection = HexSelection()
            self.selection_changed.emit(None, None)
            self.viewport().update()
            return
        start = min(max(int(start), 0), self._file_size - 1)
        end = min(max(int(end), 0), self._file_size - 1)
        self._selection = HexSelection(start, end)
        self._cursor = end
        if navigate:
            self.ensure_offset_visible(end)
        self.selection_changed.emit(self.selection_start, self.selection_end)
        self._emit_cursor()
        self.viewport().update()

    def go_to_offset(self, offset: int, *, select: bool = True) -> bool:
        if not 0 <= offset < self._file_size:
            return False
        if select:
            self._selection = HexSelection(offset, offset)
        self._cursor = offset
        self.ensure_offset_visible(offset, center=True)
        if select:
            self.selection_changed.emit(offset, offset)
        self._emit_cursor()
        self.viewport().update()
        return True

    def ensure_offset_visible(self, offset: int, *, center: bool = False) -> None:
        line = offset // self.BYTES_PER_LINE
        rows = self.visible_row_capacity
        if center:
            first = max(0, line - rows // 2)
        elif line < self._first_line:
            first = line
        elif line >= self._first_line + rows:
            first = max(0, line - rows + 1)
        else:
            first = self._first_line
        self._set_first_line(first)
        self._ensure_window(offset)

    def copy_hex(self) -> None:
        bounds = self._copy_bounds()
        if bounds is None:
            return
        data = self._cached_range(*bounds)
        if data is not None:
            QApplication.clipboard().setText(data.hex(" ").upper())
        else:
            self.copy_hex_requested.emit()

    def copy_ascii(self) -> None:
        bounds = self._copy_bounds()
        if bounds is None:
            return
        data = self._cached_range(*bounds)
        if data is not None:
            QApplication.clipboard().setText("".join(chr(value) if 32 <= value <= 126 else "." for value in data))
        else:
            self.copy_ascii_requested.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.setFont(self._font)
        palette = self.palette()
        painter.fillRect(self.viewport().rect(), palette.color(QPalette.Base))
        geometry = self.grid_geometry()
        self._paint_header(painter, geometry, palette)
        rows = self.visible_row_capacity + 2
        for row in range(rows):
            line = self._first_line + row
            offset = line * self.BYTES_PER_LINE
            if offset >= self._file_size:
                break
            y = self.HEADER_HEIGHT + row * self._row_height
            self._paint_row(painter, geometry, y, offset, palette)
        if not self._file_size:
            painter.setPen(palette.color(QPalette.PlaceholderText))
            painter.drawText(self.viewport().rect().adjusted(20, self.HEADER_HEIGHT, -20, 0),
                             Qt.AlignCenter, "Nenhum arquivo carregado")
        elif self._loading and not self._cache:
            painter.setPen(palette.color(QPalette.PlaceholderText))
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, "Carregando janela binária…")
        elif self._error:
            painter.setPen(palette.color(QPalette.PlaceholderText))
            painter.drawText(self.viewport().rect(), Qt.AlignCenter, self._error)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        offset = self.offset_at(event.position().toPoint())
        if offset is None:
            return
        extend = bool(event.modifiers() & Qt.ShiftModifier)
        anchor = self._selection.anchor if extend and self._selection.anchor is not None else offset
        self._selection = HexSelection(anchor, offset)
        self._cursor = offset
        self._dragging = True
        self.selection_changed.emit(self.selection_start, self.selection_end)
        self._emit_cursor()
        self.viewport().update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        offset = self.offset_at(event.position().toPoint())
        self._hover_offset = offset
        if self._dragging and offset is not None:
            self._selection.cursor = offset
            self._cursor = offset
            self.selection_changed.emit(self.selection_start, self.selection_end)
            self._emit_cursor()
        self.viewport().update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.LeftButton:
            self._dragging = False
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_offset = None
        self.viewport().update()
        super().leaveEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.matches(QKeySequence.Copy):
            self.copy_hex(); return
        if event.key() == Qt.Key_C and event.modifiers() & Qt.ControlModifier:
            self.copy_hex(); return
        if self._cursor is None or not self._file_size:
            return super().keyPressEvent(event)
        movement = {
            Qt.Key_Left: -1, Qt.Key_Right: 1,
            Qt.Key_Up: -self.BYTES_PER_LINE, Qt.Key_Down: self.BYTES_PER_LINE,
            Qt.Key_PageUp: -self.visible_row_capacity * self.BYTES_PER_LINE,
            Qt.Key_PageDown: self.visible_row_capacity * self.BYTES_PER_LINE,
        }.get(event.key())
        if event.key() == Qt.Key_Home:
            target = 0 if event.modifiers() & Qt.ControlModifier else self._cursor - self._cursor % 16
        elif event.key() == Qt.Key_End:
            target = self._file_size - 1 if event.modifiers() & Qt.ControlModifier else min(
                self._file_size - 1, self._cursor - self._cursor % 16 + 15)
        elif movement is not None:
            target = min(max(self._cursor + movement, 0), self._file_size - 1)
        else:
            return super().keyPressEvent(event)
        if event.modifiers() & Qt.ShiftModifier:
            anchor = self._selection.anchor if self._selection.anchor is not None else self._cursor
            self._selection = HexSelection(anchor, target)
        else:
            self._selection = HexSelection(target, target)
        self._cursor = target
        self.ensure_offset_visible(target)
        self.selection_changed.emit(self.selection_start, self.selection_end)
        self._emit_cursor()
        self.viewport().update()

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        menu = self.create_context_menu()
        if not menu.isEmpty():
            menu.exec(event.globalPos())

    def create_context_menu(self) -> QMenu:
        menu = QMenu(self)
        if self._cursor is not None:
            menu.addAction("Copy Hex", self.copy_hex)
            menu.addAction("Copy ASCII", self.copy_ascii)
            menu.addAction("Copy Offset", lambda: QApplication.clipboard().setText(f"0x{self._cursor:08X}"))
            menu.addSeparator()
            menu.addAction("Set Start Here", lambda: self.set_selection(self._cursor, self.selection_end or self._cursor))
            menu.addAction("Set End Here", lambda: self.set_selection(self.selection_start or self._cursor, self._cursor))
        if self.selection_length:
            menu.addSeparator()
            menu.addAction("Detect Type", self.detect_requested.emit)
            menu.addAction("Calculate SHA-256", self.hash_requested.emit)
            menu.addAction("Extract Selection", self.extract_requested.emit)
        return menu

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._configure_scrollbar()
        self._configure_horizontal_scrollbar()
        self._ensure_visible_pages()

    def offset_at(self, point: QPoint) -> int | None:
        if point.y() < self.HEADER_HEIGHT:
            return None
        row = (point.y() - self.HEADER_HEIGHT) // self._row_height
        line_offset = (self._first_line + row) * self.BYTES_PER_LINE
        geometry = self.grid_geometry()
        byte_index: int | None = None
        for index, cell in enumerate(geometry.hex_cells):
            if cell.left() <= point.x() <= cell.right():
                byte_index = index; break
        if byte_index is None:
            for index, cell in enumerate(geometry.ascii_cells):
                if cell.left() <= point.x() <= cell.right():
                    byte_index = index; break
        if byte_index is None:
            return None
        offset = line_offset + min(max(byte_index, 0), 15)
        return offset if offset < self._file_size else None

    def cell_rect(self, offset: int, *, ascii_zone: bool = False) -> QRect:
        geometry = self.grid_geometry()
        template = geometry.ascii_cells[offset % 16] if ascii_zone else geometry.hex_cells[offset % 16]
        line = offset // 16 - self._first_line
        return QRect(template.left(), self.HEADER_HEIGHT + line * self._row_height,
                     template.width(), self._row_height)

    def _paint_header(self, painter: QPainter, geometry: HexGridGeometry, palette: QPalette) -> None:
        painter.fillRect(QRect(0, 0, self.viewport().width(), self.HEADER_HEIGHT),
                         palette.color(QPalette.AlternateBase))
        painter.setPen(palette.color(QPalette.Mid))
        painter.drawLine(0, self.HEADER_HEIGHT - 1, self.viewport().width(), self.HEADER_HEIGHT - 1)
        painter.drawLine(geometry.offset_rect.right() + self.OFFSET_HEX_GAP // 2, 0,
                         geometry.offset_rect.right() + self.OFFSET_HEX_GAP // 2, self.viewport().height())
        painter.drawLine(geometry.hex_rect.right() + self.HEX_ASCII_GAP // 2, 0,
                         geometry.hex_rect.right() + self.HEX_ASCII_GAP // 2, self.viewport().height())
        painter.setPen(palette.color(QPalette.Text))
        painter.save(); painter.setClipRect(geometry.offset_rect)
        painter.drawText(geometry.offset_rect.adjusted(self.OFFSET_PADDING, 0, -self.OFFSET_PADDING, 0),
                         Qt.AlignVCenter | Qt.AlignRight, "OFFSET")
        painter.restore()
        painter.save(); painter.setClipRect(geometry.hex_rect)
        for index, cell in enumerate(geometry.hex_cells):
            painter.drawText(cell, Qt.AlignCenter, f"{index:02X}")
        painter.restore()
        painter.save(); painter.setClipRect(geometry.ascii_rect)
        painter.drawText(geometry.ascii_rect, Qt.AlignCenter, "ASCII")
        painter.restore()

    def _paint_row(self, painter: QPainter, geometry: HexGridGeometry, y: int,
                   offset: int, palette: QPalette) -> None:
        painter.setPen(palette.color(QPalette.PlaceholderText))
        painter.save(); painter.setClipRect(geometry.offset_rect)
        offset_row = QRect(geometry.offset_rect.left() + self.OFFSET_PADDING, y,
                           geometry.offset_rect.width() - self.OFFSET_PADDING * 2, self._row_height)
        painter.drawText(offset_row, Qt.AlignVCenter | Qt.AlignRight, f"{offset:08X}")
        painter.restore()
        bounds = self._selection.bounds
        for index in range(16):
            absolute = offset + index
            if absolute >= self._file_size:
                break
            byte = self.byte_at(absolute)
            hex_rect, ascii_rect = QRect(geometry.hex_cells[index]), QRect(geometry.ascii_cells[index])
            hex_rect.moveTop(y); ascii_rect.moveTop(y)
            selected = bounds is not None and bounds[0] <= absolute <= bounds[1]
            cursor = absolute == self._cursor
            hover = absolute == self._hover_offset
            color = QColor(45, 104, 151, 118)
            for rect, text in ((hex_rect, f"{byte:02X}" if byte is not None else "··"),
                               (ascii_rect, (chr(byte) if 32 <= byte <= 126 else ".") if byte is not None else "·")):
                clip = geometry.hex_rect if rect is hex_rect else geometry.ascii_rect
                painter.save(); painter.setClipRect(clip)
                if selected: painter.fillRect(rect.adjusted(1, 1, -1, -1), color)
                if cursor:
                    painter.setPen(QColor("#8fc7ef")); painter.drawRect(rect.adjusted(1, 1, -2, -2))
                elif hover:
                    painter.fillRect(rect.adjusted(1, 2, -1, -2), QColor(140, 158, 176, 28))
                painter.setPen(palette.color(QPalette.Text) if byte is not None else palette.color(QPalette.Mid))
                painter.drawText(rect, Qt.AlignCenter, text)
                painter.restore()

    def grid_geometry(self) -> HexGridGeometry:
        """Return the single metric-derived geometry used by paint and hit testing."""
        char_width = max(1, ceil(self._metrics.horizontalAdvance("0")))
        byte_text_width = max(char_width * 2, ceil(self._metrics.horizontalAdvance("FF")))
        byte_spacing = max(4, ceil(char_width * .55))
        minimum_cell_width = byte_text_width + byte_spacing
        offset_digits = max(8, len(f"{max(self._file_size - 1, 0):X}"))
        offset_width = ceil(self._metrics.horizontalAdvance("0" * offset_digits)) + self.OFFSET_PADDING * 2
        ascii_cell_width = max(char_width, ceil(self._metrics.horizontalAdvance("W")))
        ascii_width = ascii_cell_width * 16 + self.ASCII_PADDING * 2
        fixed_width = (self.OUTER_MARGIN * 2 + offset_width + self.OFFSET_HEX_GAP
                       + self.HEX_ASCII_GAP + ascii_width)
        minimum_width = fixed_width + minimum_cell_width * 16
        available_hex = max(minimum_cell_width * 16, self.viewport().width() - fixed_width)
        cell_width = max(minimum_cell_width, available_hex // 16)
        content_width = fixed_width + cell_width * 16
        scroll_x = self.horizontalScrollBar().value()
        offset_x = self.OUTER_MARGIN - scroll_x
        hex_x = offset_x + offset_width + self.OFFSET_HEX_GAP
        hex_width = cell_width * 16
        ascii_x = hex_x + hex_width + self.HEX_ASCII_GAP
        height = self.viewport().height()
        offset_rect = QRect(offset_x, 0, offset_width, height)
        hex_rect = QRect(hex_x, 0, hex_width, height)
        ascii_rect = QRect(ascii_x, 0, ascii_width, height)
        hex_cells = tuple(QRect(hex_x + index * cell_width, 0, cell_width, self.HEADER_HEIGHT)
                          for index in range(16))
        ascii_cells = tuple(QRect(ascii_x + self.ASCII_PADDING + index * ascii_cell_width, 0,
                                  ascii_cell_width, self.HEADER_HEIGHT) for index in range(16))
        return HexGridGeometry(offset_rect, hex_rect, ascii_rect, hex_cells, ascii_cells,
                               max(minimum_width, content_width))

    def _configure_horizontal_scrollbar(self) -> None:
        geometry = self.grid_geometry()
        maximum = max(0, geometry.minimum_width - self.viewport().width())
        bar = self.horizontalScrollBar()
        bar.setRange(0, maximum)
        bar.setPageStep(max(1, self.viewport().width()))

    def _configure_scrollbar(self) -> None:
        lines = max(1, (self._file_size + 15) // 16)
        maximum_first = max(0, lines - self.visible_row_capacity)
        bar = self.verticalScrollBar()
        bar.blockSignals(True)
        bar.setRange(0, min(maximum_first, self.SCROLL_STEPS))
        bar.setPageStep(max(1, int(bar.maximum() * self.visible_row_capacity / lines)))
        bar.setSingleStep(max(1, int(bar.maximum() / max(lines, 1))))
        bar.setValue(self._line_to_scroll(self._first_line))
        bar.blockSignals(False)

    def _scroll_changed(self, value: int) -> None:
        self._first_line = self._scroll_to_line(value)
        self._ensure_visible_pages()
        self.viewport().update()

    def _set_first_line(self, line: int) -> None:
        total_lines = (self._file_size + 15) // 16
        self._first_line = min(max(line, 0), max(0, total_lines - self.visible_row_capacity))
        self.verticalScrollBar().setValue(self._line_to_scroll(self._first_line))
        self._ensure_visible_pages()
        self.viewport().update()

    def _line_to_scroll(self, line: int) -> int:
        total_lines = max(1, (self._file_size + 15) // 16 - self.visible_row_capacity)
        return int(line * self.verticalScrollBar().maximum() / total_lines) if total_lines else 0

    def _scroll_to_line(self, value: int) -> int:
        maximum = self.verticalScrollBar().maximum()
        total_lines = max(0, (self._file_size + 15) // 16 - self.visible_row_capacity)
        return int(value * total_lines / maximum) if maximum else 0

    def _ensure_visible_pages(self) -> None:
        if not self._file_size:
            return
        first = self._first_line * 16
        last = min(self._file_size - 1, first + (self.visible_row_capacity + 2) * 16)
        self._ensure_window(first); self._ensure_window(last)

    def _ensure_window(self, offset: int) -> None:
        page = self._page_start(offset)
        if page in self._cache:
            self._cache.move_to_end(page); return
        if page in self._pending_pages:
            return
        self._pending_pages.add(page); self._loading = True; self._request_serial += 1
        length = min(self.WINDOW_BYTES, self._file_size - page)
        self.window_requested.emit(page, length, self._request_serial)

    @classmethod
    def _page_start(cls, offset: int) -> int:
        return offset // cls.WINDOW_BYTES * cls.WINDOW_BYTES

    def _copy_bounds(self) -> tuple[int, int] | None:
        return self._selection.bounds or ((self._cursor, self._cursor) if self._cursor is not None else None)

    def _cached_range(self, start: int, end: int) -> bytes | None:
        if end - start + 1 > self.WINDOW_BYTES:
            return None
        values = [self.byte_at(offset) for offset in range(start, end + 1)]
        return None if any(value is None for value in values) else bytes(value for value in values if value is not None)

    def _emit_cursor(self) -> None:
        if self._cursor is not None:
            self.cursor_changed.emit(self._cursor, self.byte_at(self._cursor))

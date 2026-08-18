from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget


class HexViewerWidget(QWidget):
    """Bounded hexadecimal presentation for payloads already fetched lazily."""

    more_requested = Signal(int)
    offset_activated = Signal(int, bool)

    def __init__(self, *, initial_limit: int = 64 * 1024, maximum_limit: int = 2 * 1024 * 1024) -> None:
        super().__init__()
        self.initial_limit = initial_limit
        self.maximum_limit = maximum_limit
        self._data = b""
        self._visible_limit = initial_limit
        self._base_offset = 0
        self._total_available = 0
        self._selection: tuple[int, int] | None = None

        self.status = QLabel("Nenhum conteúdo binário carregado.")
        self.viewer = QPlainTextEdit()
        self.viewer.setObjectName("HexViewer")
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.viewer.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.viewer.viewport().installEventFilter(self)
        self.column_header = QLabel(
            "OFFSET     00 01 02 03 04 05 06 07 08 09 0A 0B 0C 0D 0E 0F   ASCII"
        )
        self.column_header.setObjectName("HexColumnHeader")
        self.column_header.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.load_more_button = QPushButton("Carregar mais")
        self.load_more_button.clicked.connect(self.load_more)
        self.load_more_button.hide()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.status)
        layout.addWidget(self.column_header)
        layout.addWidget(self.viewer, 1)
        layout.addWidget(self.load_more_button)

    def clear(self) -> None:
        self._data = b""
        self._visible_limit = self.initial_limit
        self._base_offset = 0
        self._total_available = 0
        self._selection = None
        self.viewer.clear()
        self.status.setText("Nenhum conteúdo binário carregado.")
        self.load_more_button.hide()

    def set_loading(self) -> None:
        self.clear()
        self.status.setText("Carregando bytes sob demanda...")

    def set_error(self, category: str, message: str) -> None:
        self.clear()
        self.status.setText(f"Hex indisponível · {category} · {message}")

    def set_bytes(self, payload: bytes | bytearray | memoryview) -> None:
        self._data = bytes(payload)
        self._total_available = len(self._data)
        self._base_offset = 0
        self._visible_limit = min(self.initial_limit, self.maximum_limit)
        self._render()

    @property
    def base_offset(self) -> int:
        return self._base_offset

    @property
    def loaded_length(self) -> int:
        return len(self._data)

    def set_logical_selection(self, start: int | None, end: int | None) -> None:
        self._selection = None if start is None or end is None else (min(start, end), max(start, end))
        self._apply_selection_highlight()

    def scroll_to_offset(self, offset: int) -> None:
        relative = offset - self._base_offset
        if relative < 0 or relative >= len(self._data):
            return
        block = self.viewer.document().findBlockByNumber(relative // 16)
        cursor = QTextCursor(block)
        cursor.setPosition(block.position() + 10 + (relative % 16) * 3)
        self.viewer.setTextCursor(cursor)
        self.viewer.centerCursor()

    def set_range_bytes(self, payload: bytes | bytearray | memoryview, *, total_available: int,
                        base_offset: int = 0) -> None:
        self._data = bytes(payload)
        self._total_available = max(total_available, len(self._data))
        self._base_offset = base_offset
        self._visible_limit = min(len(self._data), self.maximum_limit)
        self._render()

    def load_more(self) -> None:
        if len(self._data) < self._total_available and len(self._data) < self.maximum_limit:
            self.more_requested.emit(min(max(len(self._data) * 2, self.initial_limit),
                                         self.maximum_limit, self._total_available))
            return
        self._visible_limit = min(max(self._visible_limit * 2, 1), self.maximum_limit)
        self._render()

    def _render(self) -> None:
        visible = self._data[:self._visible_limit]
        lines = []
        for offset in range(0, len(visible), 16):
            chunk = visible[offset:offset + 16]
            hex_part = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_part = "".join(chr(byte) if 32 <= byte <= 126 else "." for byte in chunk)
            lines.append(f"{self._base_offset + offset:08X}  {hex_part:<47}  |{ascii_part:<16}|")
        self.viewer.setPlainText("\n".join(lines))
        shown = len(visible)
        suffix = " · visualização truncada" if shown < self._total_available else ""
        self.status.setText(f"{shown:,} de {self._total_available:,} bytes{suffix}")
        self.load_more_button.setVisible(shown < self._total_available and shown < self.maximum_limit)
        self._apply_selection_highlight()

    def eventFilter(self, watched, event) -> bool:
        if watched is self.viewer.viewport() and event.type() == QEvent.MouseButtonRelease:
            cursor = self.viewer.cursorForPosition(event.position().toPoint())
            block, column = cursor.blockNumber(), cursor.positionInBlock()
            if 0 <= block * 16 < len(self._data):
                byte_in_line = min(max((column - 10) // 3, 0), 15)
                relative = block * 16 + byte_in_line
                if relative < len(self._data):
                    self.offset_activated.emit(self._base_offset + relative,
                                               bool(event.modifiers() & Qt.ShiftModifier))
        return super().eventFilter(watched, event)

    def _apply_selection_highlight(self) -> None:
        selections = []
        if self._selection is not None and self._data:
            start = max(self._selection[0], self._base_offset)
            end = min(self._selection[1], self._base_offset + len(self._data) - 1)
            if start <= end:
                first_line = (start - self._base_offset) // 16
                last_line = (end - self._base_offset) // 16
                selection_format = QTextCharFormat()
                selection_format.setBackground(QColor(44, 111, 187, 110))
                for line in range(first_line, last_line + 1):
                    line_start = max(start - self._base_offset - line * 16, 0)
                    line_end = min(end - self._base_offset - line * 16, 15)
                    block = self.viewer.document().findBlockByNumber(line)
                    cursor = QTextCursor(block)
                    cursor.setPosition(block.position() + 10 + line_start * 3)
                    cursor.setPosition(block.position() + 10 + line_end * 3 + 2, QTextCursor.KeepAnchor)
                    selection = QTextEdit.ExtraSelection()
                    selection.cursor = cursor; selection.format = selection_format
                    selections.append(selection)
        self.viewer.setExtraSelections(selections)

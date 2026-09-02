from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QAbstractListModel, QModelIndex, QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QWheelEvent
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QListView, QPushButton, QStyledItemDelegate,
    QStyle,
)

from app.settings import ApplicationPaths
from app.ui.line_icons import LineIcon


class FileStripModel(QAbstractListModel):
    PathRole = Qt.ItemDataRole.UserRole + 1
    StatusRole = Qt.ItemDataRole.UserRole + 2

    def __init__(self) -> None:
        super().__init__()
        self._paths: list[Path] = []
        self._statuses: dict[str, str] = {}

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._paths)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self._paths):
            return None
        path = self._paths[index.row()]
        if role == Qt.ItemDataRole.DisplayRole:
            return path.name
        if role == Qt.ItemDataRole.ToolTipRole:
            return path.name
        if role == self.PathRole:
            return str(path)
        if role == self.StatusRole:
            return self._statuses.get(str(path.resolve()), "pending")
        return None

    def set_files(self, paths: list[Path]) -> None:
        self.beginResetModel()
        self._paths = [Path(path) for path in paths]
        self._statuses = {str(path.resolve()): "pending" for path in self._paths}
        self.endResetModel()

    def set_status(self, path: Path | str, status: str) -> None:
        key = str(Path(path).resolve())
        self._statuses[key] = status
        for row, candidate in enumerate(self._paths):
            if str(candidate.resolve()) == key:
                index = self.index(row)
                self.dataChanged.emit(index, index, [self.StatusRole])
                return

    def row_for_path(self, path: Path | str) -> int:
        key = str(Path(path).resolve())
        return next(
            (row for row, item in enumerate(self._paths) if str(item.resolve()) == key),
            -1,
        )


class FileStripDelegate(QStyledItemDelegate):
    WIDTH = 176

    def __init__(self, paths: ApplicationPaths | None = None) -> None:
        super().__init__()
        resource = (paths or ApplicationPaths.discover()).resource(
            "app/ui/assets/icons/tabler/file.svg"
        )
        try:
            self._file_svg = resource.read_text(encoding="utf-8")
        except OSError:
            self._file_svg = ""

    def sizeHint(self, option, index: QModelIndex) -> QSize:
        return QSize(self.WIDTH, 38)

    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        painter.save()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        palette = option.palette
        rect = option.rect.adjusted(0, 0, -1, 0)
        painter.fillRect(rect, palette.highlight() if selected else palette.base())
        painter.setPen(palette.mid().color())
        painter.drawLine(rect.topRight(), rect.bottomRight())
        if selected:
            painter.setPen(QColor(palette.highlight().color()))
            painter.drawLine(rect.bottomLeft(), rect.bottomRight())
            painter.drawLine(rect.bottomLeft() + QPoint(0, -1), rect.bottomRight() + QPoint(0, -1))
        color = palette.highlightedText().color() if selected else palette.text().color()
        if self._file_svg:
            source = self._file_svg.replace("currentColor", color.name()).encode()
            renderer = QSvgRenderer(source)
            renderer.render(painter, QRectF(rect.left() + 10, rect.top() + 10, 18, 18))
        font = QFont(option.font)
        font.setWeight(QFont.Weight.Medium if selected else QFont.Weight.Normal)
        painter.setFont(font)
        painter.setPen(color)
        text_rect = rect.adjusted(36, 0, -10, 0)
        text = painter.fontMetrics().elidedText(
            str(index.data(Qt.ItemDataRole.DisplayRole)), Qt.TextElideMode.ElideRight,
            text_rect.width(),
        )
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter, text)
        painter.restore()


class FileStripView(QListView):
    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().x()
        if not delta and event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            delta = event.angleDelta().y()
        if delta:
            bar = self.horizontalScrollBar()
            bar.setValue(bar.value() - delta)
            event.accept()
            return
        super().wheelEvent(event)


class FileStrip(QFrame):
    selection_requested = Signal(Path)

    def __init__(self, paths: ApplicationPaths | None = None) -> None:
        super().__init__()
        self.paths = paths or ApplicationPaths.discover()
        self.setObjectName("FileStrip")
        self.model = FileStripModel()
        self.view = FileStripView()
        self.view.setObjectName("FileStripView")
        self.view.setModel(self.model)
        self.view.setItemDelegate(FileStripDelegate(self.paths))
        self.view.setFlow(QListView.Flow.LeftToRight)
        self.view.setWrapping(False)
        self.view.setUniformItemSizes(True)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.view.setFixedHeight(48)
        self.view.clicked.connect(self._emit_selection)
        self.previous_button = self._scroll_button("chevron-left", "Arquivos anteriores", -1)
        self.next_button = self._scroll_button("chevron-right", "Próximos arquivos", 1)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.previous_button)
        layout.addWidget(self.view, stretch=1)
        layout.addWidget(self.next_button)
        self.setVisible(False)

    def _scroll_button(self, icon: str, tooltip: str, direction: int) -> QPushButton:
        button = QPushButton()
        button.setObjectName("FileStripScrollButton")
        button.setFixedWidth(32)
        button.setToolTip(tooltip)
        button.setAccessibleName(tooltip)
        row = QHBoxLayout(button)
        row.setContentsMargins(7, 0, 7, 0)
        row.addWidget(LineIcon(icon, button, 16, paths=self.paths))
        button.clicked.connect(lambda: self._scroll(direction))
        return button

    def set_files(self, paths: list[Path]) -> None:
        self.model.set_files(paths)
        self.setVisible(bool(paths))
        if paths:
            self.set_selected_path(paths[0])

    def set_status(self, path: Path | str, status: str) -> None:
        self.model.set_status(path, status)

    def set_selected_path(self, path: Path | str) -> None:
        row = self.model.row_for_path(path)
        if row < 0:
            return
        index = self.model.index(row)
        self.view.setCurrentIndex(index)
        self.view.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)

    def selected_path(self) -> Path | None:
        index = self.view.currentIndex()
        raw = index.data(FileStripModel.PathRole) if index.isValid() else None
        return Path(str(raw)) if raw else None

    def _emit_selection(self, index: QModelIndex) -> None:
        raw = index.data(FileStripModel.PathRole)
        if raw:
            self.selection_requested.emit(Path(str(raw)))

    def _scroll(self, direction: int) -> None:
        bar = self.view.horizontalScrollBar()
        bar.setValue(bar.value() + direction * FileStripDelegate.WIDTH * 2)

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, QSize, Qt
from PySide6.QtGui import QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QHBoxLayout, QWidget

from app.settings import ApplicationPaths


class LineIcon(QWidget):
    """Palette-aware renderer for a local Tabler SVG asset."""

    def __init__(
        self,
        name: str,
        parent: QWidget | None = None,
        size: int = 18,
        *,
        paths: ApplicationPaths | None = None,
    ) -> None:
        super().__init__(parent)
        self.name = name
        self.paths = paths or ApplicationPaths.discover()
        self.setObjectName("SvgIcon")
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        icon_path = self.paths.resource(f"app/ui/assets/icons/tabler/{name}.svg")
        try:
            self._source = icon_path.read_text(encoding="utf-8")
        except OSError:
            self._source = ""

    @property
    def has_asset(self) -> bool:
        return bool(self._source)

    def sizeHint(self) -> QSize:
        return self.size()

    def paintEvent(self, event) -> None:
        if not self._source:
            return
        color = self.palette().color(self.foregroundRole()).name()
        renderer = QSvgRenderer(QByteArray(self._source.replace("currentColor", color).encode()))
        painter = QPainter(self)
        renderer.render(painter, QRectF(0, 0, self.width(), self.height()))


class HomeIllustration(QWidget):
    """Small composition made exclusively from local Tabler SVG assets."""

    def __init__(self, parent: QWidget | None = None, *, paths: ApplicationPaths | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeIllustration")
        self.setFixedSize(132, 64)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 12, 4)
        layout.setSpacing(14)
        layout.addWidget(LineIcon("file", self, 34, paths=paths))
        layout.addWidget(LineIcon("topology-star", self, 42, paths=paths))
        layout.addWidget(LineIcon("file-search", self, 34, paths=paths))

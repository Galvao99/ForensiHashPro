from PySide6.QtCore import Qt
from PySide6.QtGui import QFontMetrics, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class CurrentFileBadge(QLabel):
    """Badge compacto que identifica o arquivo exibido pela página."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._file_name = ""
        self.setObjectName("CurrentFileBadge")
        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)
        self.setMinimumWidth(80)
        self.setMaximumWidth(320)
        self.setVisible(False)

    @property
    def file_name(self) -> str:
        return self._file_name

    def set_file_name(self, file_name: str | None) -> None:
        self._file_name = str(file_name or "")
        self.setToolTip(self._file_name)
        self.setVisible(bool(self._file_name))
        self._update_elided_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_elided_text()

    def _update_elided_text(self) -> None:
        if not self._file_name:
            self.clear()
            return
        available_width = max(0, self.width() - 24)
        metrics = QFontMetrics(self.font())
        self.setText(
            metrics.elidedText(
                self._file_name,
                Qt.ElideMiddle,
                available_width,
            )
        )

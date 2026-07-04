from pathlib import Path

from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)

from app.models import MagicNumberResult
from app.widgets.binary_analyzer.hex_dialog import HexDialog


class HexPreviewCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BinaryCard")

        self.file_path: Path | None = None

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("🔎 Visualização do Cabeçalho HEX")
        title.setObjectName("CardTitle")

        self.viewer = QPlainTextEdit()
        self.viewer.setObjectName("HexPreview")
        self.viewer.setReadOnly(True)
        self.viewer.setMaximumHeight(180)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        self.expand_button = QPushButton("Expandir HEX")
        self.expand_button.setObjectName("PrimaryButton")
        self.expand_button.clicked.connect(self.open_full_hex)

        layout.addWidget(title)
        layout.addWidget(self.viewer)
        layout.addWidget(self.expand_button)

    def update_result(
        self,
        result: MagicNumberResult,
        file_path: Path | None = None,
    ) -> None:
        self.file_path = file_path
        self.viewer.setPlainText(result.header_preview_hex or "")

    def open_full_hex(self) -> None:
        if not self.file_path:
            return

        dialog = HexDialog(self.file_path, self)
        dialog.exec()
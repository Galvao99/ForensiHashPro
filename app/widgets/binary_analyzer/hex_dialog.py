from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)


class HexDialog(QDialog):
    def __init__(self, file_path: Path | None = None, parent=None) -> None:
        super().__init__(parent)

        self.file_path = file_path
        self.setWindowTitle("Binary Explorer - HEX completo")
        self.resize(1100, 750)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar texto ou HEX...")

        self.search_button = QPushButton("Buscar")
        self.search_button.clicked.connect(self.search)

        self.viewer = QPlainTextEdit()
        self.viewer.setObjectName("HexViewer")
        self.viewer.setReadOnly(True)
        self.viewer.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        top = QHBoxLayout()
        top.addWidget(QLabel("Pesquisar:"))
        top.addWidget(self.search_input)
        top.addWidget(self.search_button)

        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.viewer)

        if self.file_path:
            self.load_file(self.file_path)

    def load_file(self, file_path: Path) -> None:
        data = file_path.read_bytes()
        self.viewer.setPlainText(self._hex_dump(data))

    def search(self) -> None:
        query = self.search_input.text().strip()

        if not query:
            return

        document = self.viewer.document()
        cursor = document.find(query)

        if not cursor.isNull():
            self.viewer.setTextCursor(cursor)
            self.viewer.setFocus()

    def _hex_dump(self, data: bytes, width: int = 16) -> str:
        lines = []

        for offset in range(0, len(data), width):
            chunk = data[offset:offset + width]
            hex_part = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_part = "".join(
                chr(byte) if 32 <= byte <= 126 else "."
                for byte in chunk
            )

            lines.append(
                f"{offset:08X}  {hex_part:<48}  {ascii_part}"
            )

        return "\n".join(lines)
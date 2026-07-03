from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QLineEdit, QTextEdit, QVBoxLayout, QWidget


class OcrTextViewer(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("OcrTextViewer")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar palavra, número, data, IP...")
        self.search_input.textChanged.connect(self.highlight_search)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setObjectName("OcrTextArea")

        layout = QVBoxLayout(self)
        layout.addWidget(self.search_input)
        layout.addWidget(self.text_area)

    def set_text(self, text: str) -> None:
        self.text_area.setPlainText(text or "Nenhum texto foi extraído do arquivo.")

    def highlight_search(self, term: str) -> None:
        cursor = self.text_area.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.setCharFormat(QTextCharFormat())
        cursor.clearSelection()
        self.text_area.setTextCursor(cursor)

        if not term.strip():
            return

        highlight_format = QTextCharFormat()
        highlight_format.setBackground(QColor("#FEF3C7"))
        highlight_format.setForeground(QColor("#92400E"))

        document = self.text_area.document()
        cursor = QTextCursor(document)

        while True:
            cursor = document.find(term, cursor)

            if cursor.isNull():
                break

            cursor.mergeCharFormat(highlight_format)
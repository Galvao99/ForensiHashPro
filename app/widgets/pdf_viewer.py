from pathlib import Path

import fitz
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget


class PdfViewer(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("PdfViewer")

        self.zoom = 1.4
        self.file_path: Path | None = None

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)

        self.container = QWidget()
        self.layout = QVBoxLayout(self.container)
        self.layout.setAlignment(Qt.AlignTop)

        self.scroll.setWidget(self.container)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll)

    def load_pdf(self, file_path: str | Path) -> None:
        self.file_path = Path(file_path)
        self._clear_pages()

        if self.file_path.suffix.lower() != ".pdf":
            label = QLabel("Visualização disponível apenas para arquivos PDF.")
            label.setAlignment(Qt.AlignCenter)
            self.layout.addWidget(label)
            return

        try:
            doc = fitz.open(self.file_path)

            for page_index in range(len(doc)):
                page = doc[page_index]
                matrix = fitz.Matrix(self.zoom, self.zoom)
                pix = page.get_pixmap(matrix=matrix, alpha=False)

                image = QImage(
                    pix.samples,
                    pix.width,
                    pix.height,
                    pix.stride,
                    QImage.Format_RGB888,
                )

                page_label = QLabel()
                page_label.setAlignment(Qt.AlignCenter)
                page_label.setPixmap(QPixmap.fromImage(image.copy()))
                page_label.setObjectName("PdfPageImage")

                self.layout.addWidget(page_label)

            doc.close()

        except Exception as error:
            label = QLabel(f"Erro ao renderizar PDF: {error}")
            label.setWordWrap(True)
            self.layout.addWidget(label)

    def _clear_pages(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.services.text_extraction_service import TextExtractionService
from app.widgets.ocr_text_viewer import OcrTextViewer
from app.widgets.pdf_viewer import PdfViewer


class OcrPage(QWidget):
    """Página de OCR e visualização textual do documento."""

    def __init__(self) -> None:
        super().__init__()

        self.text_service = TextExtractionService()

        self.pdf_viewer = PdfViewer()
        self.ocr_viewer = OcrTextViewer()

        title = QLabel("OCR e Busca no Documento")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Visualize o PDF analisado, extraia o texto do contrato e pesquise por palavras, datas, números ou IPs."
        )
        subtitle.setObjectName("SectionSubtitle")
        subtitle.setWordWrap(True)

        content_layout = QHBoxLayout()
        content_layout.addWidget(self.pdf_viewer, 2)
        content_layout.addWidget(self.ocr_viewer, 1)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(content_layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        file_path = result.file_info.path

        self.pdf_viewer.load_pdf(file_path)

        text = self.text_service.extract_text(file_path)
        self.ocr_viewer.set_text(text)
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult
from app.widgets.ocr_text_viewer import OcrTextViewer
from app.widgets.pdf_viewer import PdfViewer


class OcrPage(QWidget):
    """
    Página de visualização do documento e do texto extraído.
    """

    def __init__(self) -> None:
        super().__init__()

        self.pdf_viewer = PdfViewer()
        self.ocr_viewer = OcrTextViewer()

        title = QLabel(
            "OCR e Busca no Documento"
        )
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Visualize o arquivo analisado e pesquise no texto "
            "extraído por palavras, datas, documentos ou IPs."
        )
        subtitle.setObjectName(
            "SectionSubtitle"
        )
        subtitle.setWordWrap(True)

        content_layout = QHBoxLayout()
        content_layout.setSpacing(14)
        content_layout.addWidget(
            self.pdf_viewer,
            2,
        )
        content_layout.addWidget(
            self.ocr_viewer,
            1,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(12)

        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addLayout(content_layout)

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        file_path = result.file_info.path

        self.pdf_viewer.load_pdf(
            file_path
        )

        text = getattr(
            result,
            "extracted_text",
            "",
        )

        self.ocr_viewer.set_text(
            text
            or "Nenhum conteúdo textual foi extraído."
        )
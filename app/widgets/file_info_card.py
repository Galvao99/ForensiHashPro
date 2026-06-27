from PySide6.QtWidgets import QLabel

from app.models import AnalysisResult
from app.widgets.base_card import BaseCard


class FileInfoCard(BaseCard):
    """Card de informações do arquivo."""

    def __init__(self) -> None:
        super().__init__("📄 Informações do Arquivo")

        self.content_label = QLabel("Nenhum arquivo selecionado.")
        self.content_label.setObjectName("CardContent")
        self.content_label.setWordWrap(True)

        self.body_layout.addWidget(self.content_label)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.content_label.setText(
            f"""Nome: {result.file_info.name}
Extensão: {result.file_info.extension}
Tamanho: {result.file_info.size_bytes:,} bytes
Analisado em: {result.analyzed_at.strftime("%d/%m/%Y %H:%M:%S")}"""
        )
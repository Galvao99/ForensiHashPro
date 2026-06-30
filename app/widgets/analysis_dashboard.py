from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from app.knowledge.summary_builder import SummaryBuilder
from app.models import AnalysisResult
from app.widgets.file_info_card import FileInfoCard
from app.widgets.finding_preview_card import FindingsPreviewCard
from app.widgets.summary_card import SummaryCard


class AnalysisDashboard(QWidget):
    """Painel geral da análise.

    A aba Geral deve funcionar como uma visão executiva:
    - resumo pericial;
    - informações principais do arquivo;
    - prévia dos vestígios;
    - sem excesso de dados brutos.
    """

    def __init__(self) -> None:
        super().__init__()

        self.summary_builder = SummaryBuilder()

        self.title_label = QLabel("Nenhum arquivo selecionado.")
        self.title_label.setObjectName("DashboardTitle")

        self.summary_card = SummaryCard()
        self.file_info_card = FileInfoCard()
        self.findings_preview_card = FindingsPreviewCard()

        grid = QGridLayout()
        grid.setSpacing(16)

        grid.addWidget(self.file_info_card, 0, 0)
        grid.addWidget(self.findings_preview_card, 0, 1)

        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self.title_label)
        layout.addWidget(self.summary_card)
        layout.addLayout(grid)
        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.title_label.setText(f"Arquivo atual: {result.file_info.name}")

        summary = self.summary_builder.build(result)
        self.summary_card.update_summary(summary)

        self.file_info_card.update_analysis(result)
        self.findings_preview_card.update_findings(result.findings)
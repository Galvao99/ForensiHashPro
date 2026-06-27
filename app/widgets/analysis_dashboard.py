from PySide6.QtWidgets import QGridLayout, QLabel, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.file_info_card import FileInfoCard
from app.widgets.hash_card import HashCard
from app.widgets.finding_card import FindingCard

class AnalysisDashboard(QWidget):
    """Painel principal de exibição da análise."""

    def __init__(self) -> None:
        super().__init__()

        self.title_label = QLabel("Nenhum arquivo selecionado.")
        self.title_label.setObjectName("DashboardTitle")

        self.file_info_card = FileInfoCard()
        self.hash_card = HashCard()
        self.findings_card = FindingCard()

        grid = QGridLayout()
        grid.setSpacing(16)

        grid.addWidget(self.file_info_card, 0, 0)
        grid.addWidget(self.hash_card, 0, 1)
        grid.addWidget(self.findings_card, 1, 0, 1, 2)

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addLayout(grid)
        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.title_label.setText(f"Arquivo atual: {result.file_info.name}")

        self.file_info_card.update_analysis(result)
        self.hash_card.update_hashes(result.hashes)
        self.findings_card.update_findings(result.findings)

    
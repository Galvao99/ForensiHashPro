from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.finding_card import FindingCard


class FindingPage(QWidget):
    """Página dedicada aos vestígios técnicos interpretados."""

    def __init__(self) -> None:
        super().__init__()

        self.finding_card = FindingCard()

        layout = QVBoxLayout()
        layout.addWidget(self.finding_card)

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.finding_card.update_findings(result.findings)
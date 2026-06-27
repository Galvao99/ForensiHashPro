from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.finding_list import FindingList


class FindingPage(QWidget):
    """Página dedicada aos vestígios técnicos."""

    def __init__(self) -> None:
        super().__init__()

        self.finding_list = FindingList()

        layout = QVBoxLayout()
        layout.addWidget(self.finding_list)

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.finding_list.update_findings(result.findings)
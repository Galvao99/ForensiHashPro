from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.analysis_dashboard import AnalysisDashboard


class GeneralPage(QWidget):
    """Página geral da análise."""

    def __init__(self) -> None:
        super().__init__()

        self.dashboard = AnalysisDashboard()

        layout = QVBoxLayout()
        layout.addWidget(self.dashboard)

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.dashboard.update_analysis(result)
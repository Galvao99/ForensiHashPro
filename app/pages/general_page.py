from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.analysis_dashboard import AnalysisDashboard
from app.investigation.correlation_result import CorrelationResult


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

    def update_correlation_count(self, count: int) -> None:
        self.dashboard.update_correlation_count(count)

    def update_case(
        self,
        state: dict[str, object],
        results: list[AnalysisResult],
        correlation: CorrelationResult | None,
    ) -> None:
        self.dashboard.update_case(state, results, correlation)

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import QFrame, QLabel, QScrollArea, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.finding_preview_card import FindingsPreviewCard
from app.widgets.forensic_summary import ForensicSummary
from app.widgets.result_header import ResultHeader
from app.widgets.case_overview import CaseOverview
from app.investigation.correlation_result import CorrelationResult


class AnalysisDashboard(QWidget):
    """Síntese factual do artefato selecionado."""

    RESPONSIVE_BREAKPOINT = 900

    def __init__(self) -> None:
        super().__init__()
        self.current_result: AnalysisResult | None = None
        self.correlation_count: int | None = None
        self.case_overview = CaseOverview()

        self.result_header = ResultHeader()
        self.summary_eyebrow = QLabel("ARQUIVO SELECIONADO")
        self.summary_eyebrow.setObjectName("SummaryEyebrow")
        self.summary_title = QLabel("Resumo Forense")
        self.summary_title.setObjectName("ForensicSummaryTitle")
        self.summary_description = QLabel(
            "Síntese dos fatos técnicos observados. Os detalhes permanecem nas páginas específicas."
        )
        self.summary_description.setObjectName("ForensicSummaryDescription")
        self.summary_description.setWordWrap(True)
        self.forensic_summary = ForensicSummary()
        self.findings_preview_card = FindingsPreviewCard()

        content = QWidget()
        content.setObjectName("DashboardContent")
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(4, 4, 10, 18)
        self.content_layout.setSpacing(14)
        self.content_layout.addWidget(self.case_overview)
        self.content_layout.addWidget(self.result_header)
        self.content_layout.addSpacing(4)
        self.content_layout.addWidget(self.summary_eyebrow)
        self.content_layout.addWidget(self.summary_title)
        self.content_layout.addWidget(self.summary_description)
        self.content_layout.addWidget(self.forensic_summary)
        self.content_layout.addWidget(self.findings_preview_card)
        self.content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setObjectName("DashboardScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def resizeEvent(self, event: QEvent) -> None:
        compact = event.size().width() < self.RESPONSIVE_BREAKPOINT
        self.forensic_summary.set_compact(compact)
        self.forensic_summary.sections_layout.setHorizontalSpacing(8 if compact else 12)
        super().resizeEvent(event)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.current_result = result
        self.correlation_count = None
        self.result_header.update_analysis(result)
        self.forensic_summary.update_analysis(result)
        self.findings_preview_card.update_findings(result.findings)

    def update_correlation_count(self, count: int) -> None:
        self.correlation_count = count

    def update_case(
        self,
        state: dict[str, object],
        results: list[AnalysisResult],
        correlation: CorrelationResult | None,
    ) -> None:
        self.case_overview.update_case(state, results, correlation)

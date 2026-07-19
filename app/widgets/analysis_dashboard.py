from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

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

    RESPONSIVE_BREAKPOINT = 900

    def __init__(self) -> None:
        super().__init__()

        self.summary_builder = SummaryBuilder()
        self.current_result: AnalysisResult | None = None
        self.correlation_count: int | None = None

        self.title_label = QLabel("Nenhum arquivo selecionado.")
        self.title_label.setObjectName("DashboardTitle")
        self.subtitle_label = QLabel(
            "Síntese factual da análise do arquivo atualmente selecionado."
        )
        self.subtitle_label.setObjectName("DashboardSubtitle")
        self.subtitle_label.setWordWrap(True)

        self.summary_card = SummaryCard()
        self.file_info_card = FileInfoCard()
        self.findings_preview_card = FindingsPreviewCard()

        self.cards_grid = QGridLayout()
        self.cards_grid.setSpacing(16)

        self.cards_grid.addWidget(self.file_info_card, 0, 0)
        self.cards_grid.addWidget(self.findings_preview_card, 0, 1)
        self.cards_grid.setColumnStretch(0, 1)
        self.cards_grid.setColumnStretch(1, 1)

        content = QWidget()
        content.setObjectName("DashboardContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 8, 12)
        content_layout.setSpacing(16)

        header = QFrame()
        header.setObjectName("DashboardHeader")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(18, 15, 18, 15)
        header_layout.setSpacing(4)
        header_layout.addWidget(self.title_label)
        header_layout.addWidget(self.subtitle_label)

        content_layout.addWidget(header)
        content_layout.addWidget(self.summary_card)
        content_layout.addLayout(self.cards_grid)
        content_layout.addStretch()

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
        target = (1, 0) if compact else (0, 1)
        index = self.cards_grid.indexOf(self.findings_preview_card)
        current = self.cards_grid.getItemPosition(index)[:2]
        if current != target:
            self.cards_grid.removeWidget(self.findings_preview_card)
            self.cards_grid.addWidget(self.findings_preview_card, *target)
        super().resizeEvent(event)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.current_result = result
        self.correlation_count = None
        self.title_label.setText(f"Arquivo atual: {result.file_info.name}")

        summary = self.summary_builder.build(
            result,
            correlation_count=self.correlation_count,
        )
        self.summary_card.update_summary(summary)

        self.file_info_card.update_analysis(result)
        self.findings_preview_card.update_findings(result.findings)

    def update_correlation_count(self, count: int) -> None:
        self.correlation_count = count
        if self.current_result is not None:
            self.summary_card.update_summary(
                self.summary_builder.build(
                    self.current_result,
                    correlation_count=count,
                )
            )

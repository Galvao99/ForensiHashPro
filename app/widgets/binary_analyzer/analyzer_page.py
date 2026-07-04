from pathlib import Path

from PySide6.QtWidgets import (
    QGridLayout,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult
from app.widgets.binary_analyzer.finding_table import FindingsTable
from app.widgets.binary_analyzer.hex_preview_card import HexPreviewCard
from app.widgets.binary_analyzer.interpretation_card import InterpretationCard
from app.widgets.binary_analyzer.search_toolbar import SearchToolbar
from app.widgets.binary_analyzer.summary_card import SummaryCard
from app.widgets.binary_analyzer.technical_card import TechnicalCard


class BinaryAnalyzerPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.toolbar = SearchToolbar()
        self.summary_card = SummaryCard()
        self.technical_card = TechnicalCard()
        self.hex_preview_card = HexPreviewCard()
        self.findings_table = FindingsTable()
        self.interpretation_card = InterpretationCard()

        content = QWidget()
        grid = QGridLayout(content)
        grid.setContentsMargins(14, 14, 14, 14)
        grid.setSpacing(14)

        grid.addWidget(self.toolbar, 0, 0, 1, 2)
        grid.addWidget(self.summary_card, 1, 0)
        grid.addWidget(self.technical_card, 1, 1)
        grid.addWidget(self.findings_table, 2, 0)
        grid.addWidget(self.hex_preview_card, 2, 1)
        grid.addWidget(self.interpretation_card, 3, 0, 1, 2)

        grid.setColumnStretch(0, 3)
        grid.setColumnStretch(1, 2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def update_analysis(self, result: AnalysisResult) -> None:
        magic = result.magic_numbers

        file_path = None
        if hasattr(result, "file_info") and result.file_info:
            raw_path = getattr(result.file_info, "path", None)
            if raw_path:
                file_path = Path(raw_path)

        self.summary_card.update_result(magic)
        self.technical_card.update_result(magic)
        self.findings_table.update_result(magic)
        self.hex_preview_card.update_result(magic, file_path)
        self.interpretation_card.update_result(magic)
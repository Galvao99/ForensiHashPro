from PySide6.QtWidgets import QFrame, QScrollArea, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.current_file_badge import CurrentFileBadge
from app.widgets.document_structure_card import DocumentStructureCard
from app.widgets.integrity_card import IntegrityCard


class IntegrityPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.current_file_badge = CurrentFileBadge()
        self.card = IntegrityCard()
        self.structure_card = DocumentStructureCard()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setSpacing(14)
        content_layout.addWidget(self.current_file_badge)
        content_layout.addWidget(self.card)
        content_layout.addWidget(self.structure_card)
        content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(content)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(scroll)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.current_file_badge.set_file_name(result.file_info.name)
        self.card.update_integrity(result)
        binary_analysis = result.binary_analysis
        pdf_raw_analysis = (
            binary_analysis.pdf_raw_analysis
            if binary_analysis is not None
            else None
        )
        self.structure_card.update_result(pdf_raw_analysis)

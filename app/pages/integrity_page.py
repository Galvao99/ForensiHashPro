from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.integrity_card import IntegrityCard


class IntegrityPage(QWidget):
    def __init__(self):
        super().__init__()

        self.card = IntegrityCard()

        layout = QVBoxLayout()
        layout.addWidget(self.card)
        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.card.update_integrity(result)
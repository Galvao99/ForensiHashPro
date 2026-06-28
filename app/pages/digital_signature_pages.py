from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.digital_signature_card import DigitalSignatureCard


class DigitalSignaturePage(QWidget):

    def __init__(self):

        super().__init__()

        self.card = DigitalSignatureCard()

        layout = QVBoxLayout()

        layout.addWidget(self.card)

        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(
        self,
        result: AnalysisResult,
    ):

        self.card.update_signature(
            result.digital_signature
        )
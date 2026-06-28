from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.magic_number_card import MagicNumberCard


class MagicNumberPage(QWidget):
    """Página de Magic Number."""

    def __init__(self) -> None:
        super().__init__()

        self.magic_number_card = MagicNumberCard()

        layout = QVBoxLayout()
        layout.addWidget(self.magic_number_card)
        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.magic_number_card.update_magic_number(result.magic_numbers)
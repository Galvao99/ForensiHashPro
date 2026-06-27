from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.hash_card import HashCard


class HashPage(QWidget):
    """Página dedicada aos hashes."""

    def __init__(self) -> None:
        super().__init__()

        self.hash_card = HashCard()

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        layout.addWidget(self.hash_card)
        layout.addStretch()

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.hash_card.update_hashes(result.hashes)
        self.hash_card.update()
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.models.comparison_result import ComparisonResult
from app.widgets.comparison_card import ComparisonCard


class ComparisonPage(QWidget):
    
    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Comparação Forense")
        title.setObjectName("PageTitle")

        self.card = ComparisonCard()

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(self.card)
        layout.addStretch()

        self.setLayout(layout)

    def update_comparison(self, result: ComparisonResult) -> None:
        self.card.update_comparison(result)
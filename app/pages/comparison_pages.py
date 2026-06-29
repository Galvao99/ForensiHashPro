from PySide6.QtWidgets import QLabel, QProgressBar, QVBoxLayout, QWidget

from app.models.comparison_result import ComparisonResult
from app.widgets.comparison_card import ComparisonCard


class ComparisonPage(QWidget):
    """Página de comparação forense."""

    def __init__(self) -> None:
        super().__init__()

        self.title = QLabel("Comparação Forense")
        self.title.setObjectName("PageTitle")

        self.summary_label = QLabel("Aguardando comparação.")
        self.summary_label.setObjectName("DashboardTitle")
        self.summary_label.setWordWrap(True)

        self.similarity_bar = QProgressBar()
        self.similarity_bar.setRange(0, 100)
        self.similarity_bar.setValue(0)
        self.similarity_bar.setTextVisible(True)

        self.card = ComparisonCard()

        layout = QVBoxLayout()
        layout.setSpacing(16)

        layout.addWidget(self.title)
        layout.addWidget(self.summary_label)
        layout.addWidget(self.similarity_bar)
        layout.addWidget(self.card)
        layout.addStretch()

        self.setLayout(layout)

    def update_comparison(self, result: ComparisonResult) -> None:
        total = len(result.sections)

        if total == 0:
            score = 0
        else:
            success_count = sum(
                1 for section in result.sections
                if section.status == "success"
            )
            score = int((success_count / total) * 100)

        self.summary_label.setText(result.technical_summary)
        self.similarity_bar.setValue(score)
        self.card.update_comparison(result)
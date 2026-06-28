from PySide6.QtWidgets import QLabel

from app.widgets.base_card import BaseCard


class ComparisonCard(BaseCard):
    """Card responsável pela exibição da comparação entre duas análises."""

    def __init__(self) -> None:
        super().__init__("🆚 Comparação Forense")

        self.content = QLabel("Comparação ainda não realizada.")
        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)
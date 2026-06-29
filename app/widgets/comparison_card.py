from PySide6.QtWidgets import QLabel

from app.widgets.base_card import BaseCard


class ComparisonCard(BaseCard):
    """Card genérico para módulos da comparação."""

    def __init__(self, title: str = "⚖ Comparação") -> None:
        super().__init__(title)

        self.content = QLabel("Nenhuma comparação realizada.")
        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)

    def update_text(self, text: str) -> None:
        self.content.setText(text)
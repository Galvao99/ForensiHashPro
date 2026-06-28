from app.models import MagicNumberResult
from app.widgets.base_card import BaseCard
from PySide6.QtWidgets import QLabel


class MagicNumberCard(BaseCard):
    """Card responsável pela exibição do Magic Number."""

    def __init__(self) -> None:
        super().__init__("🧬 Magic Number")

        self.content = QLabel("Nenhum arquivo analisado.")
        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)

    def update_magic_number(self, magic_number: MagicNumberResult) -> None:
        status = "Compatível com a extensão" if magic_number.extension_matches else "Incompatível ou desconhecido"

        self.content.setText(
            f"""Tipo detectado:
{magic_number.detected_type}

Magic Number (assinatura binária):
{magic_number.signature}

Status:
{status}"""
        )
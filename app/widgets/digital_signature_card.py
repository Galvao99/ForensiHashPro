from PySide6.QtWidgets import QLabel

from app.models import DigitalSignatureResult
from app.widgets.base_card import BaseCard


class DigitalSignatureCard(BaseCard):
    """Card da assinatura digital."""

    def __init__(self) -> None:
        super().__init__("🔏 Assinatura Digital")

        self.content = QLabel(
            "Nenhuma análise realizada."
        )

        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)

    def update_signature(
        self,
        signature: DigitalSignatureResult,
    ) -> None:

        if not signature.has_signature:

            self.content.setText(
                f"""🟡 Nenhuma assinatura digital encontrada.

{signature.technical_status}
"""
            )

            return

        self.content.setText(
            f"""🟢 Assinatura Digital Encontrada

Quantidade...........: {signature.signature_count}

Assinante............: {signature.signer or "-"}

Emissor..............: {signature.issuer or "-"}

Serial...............: {signature.serial_number or "-"}

Algoritmo............: {signature.algorithm or "-"}

Assinado em..........: {signature.signing_time or "-"}

Timestamp............: {signature.timestamp or "-"}

Válido de............: {signature.valid_from or "-"}

Válido até...........: {signature.valid_until or "-"}

Status...............: {signature.technical_status}
"""
        )
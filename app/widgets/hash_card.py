from PySide6.QtWidgets import QLabel

from app.models import HashResult
from app.widgets.base_card import BaseCard


class HashCard(BaseCard):
    """Card responsável pela exibição dos hashes."""

    def __init__(self) -> None:
        super().__init__("🔐 Hashes")

        self.content = QLabel("-")
        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)

    def update_hashes(
        self,
        hashes: HashResult,
    ) -> None:

        self.content.setText(
            f"""MD5
{hashes.md5}

SHA-1
{hashes.sha1}

SHA-224
{hashes.sha224}

SHA-256
{hashes.sha256}

SHA-384
{hashes.sha384}

SHA-512
{hashes.sha512}
"""
        )
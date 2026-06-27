from PySide6.QtWidgets import QLabel

from app.models import Finding
from app.widgets.base_card import BaseCard


class FindingCard(BaseCard):
    """Card responsável pelos vestígios encontrados."""

    def __init__(self) -> None:

        super().__init__("⚠ Vestígios Técnicos")

        self.content = QLabel(
            "Nenhum vestígio encontrado."
        )

        self.content.setWordWrap(True)

        self.content.setObjectName("CardContent")

        self.body_layout.addWidget(self.content)

    def update_findings(
        self,
        findings: list[Finding],
    ) -> None:

        if not findings:

            self.content.setText(
                "Nenhum vestígio técnico foi identificado."
            )

            return

        text = ""

        for finding in findings:

            text += (
                f"{finding.severity.value.upper()} | {finding.category}\n"
                f"{finding.title}\n\n"
                f"{finding.description}\n\n"
                f"Fonte: {finding.evidence_source or '-'}\n"
                f"Valor: {finding.observed_value or '-'}\n"
                f"Recomendação: {finding.recommendation or '-'}\n"
                f"Confiança: {finding.score:.0%}\n\n"
                "──────────────────────────────\n\n"
            )

        self.content.setText(text)
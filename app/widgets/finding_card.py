from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from app.models import Finding
from app.widgets.base_card import BaseCard
from app.widgets.finding_item_card import FindingItemCard


class FindingCard(BaseCard):
    """Painel robusto dos vestígios técnicos encontrados."""

    def __init__(self) -> None:
        super().__init__("🧩 Vestígios Correlacionados")

        self.subtitle = QLabel(
            "Ponto de convergência entre metadados, hashes, magic number, assinatura digital, "
            "timeline e demais elementos técnicos."
        )
        self.subtitle.setObjectName("FindingSubtitle")
        self.subtitle.setWordWrap(True)

        self.items_container = QWidget()
        self.items_layout = QVBoxLayout(self.items_container)
        self.items_layout.setSpacing(12)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(self.items_container)
        self.scroll_area.setObjectName("FindingScrollArea")

        self.body_layout.addWidget(self.subtitle)
        self.body_layout.addWidget(self.scroll_area)

    def update_findings(self, findings: list[Finding]) -> None:
        self._clear_items()

        if not findings:
            empty = QLabel(
                "Nenhum vestígio técnico foi identificado. "
                "Quando houver inconsistências, producers relevantes, divergências temporais "
                "ou ausência de elementos verificáveis, eles aparecerão nesta área."
            )
            empty.setObjectName("FindingEmptyText")
            empty.setWordWrap(True)
            self.items_layout.addWidget(empty)
            self.items_layout.addStretch()
            return

        ordered_findings = self._sort_findings(findings)

        for finding in ordered_findings:
            self.items_layout.addWidget(FindingItemCard(finding))

        self.items_layout.addStretch()

    def _clear_items(self) -> None:
        while self.items_layout.count():
            item = self.items_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def _sort_findings(self, findings: list[Finding]) -> list[Finding]:
        severity_order = {
            "critical": 0,
            "warning": 1,
            "info": 2,
            "success": 3,
        }

        return sorted(
            findings,
            key=lambda finding: (
                severity_order.get(finding.severity.value.lower(), 9),
                -finding.score,
            ),
        )
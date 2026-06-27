from PySide6.QtWidgets import QListWidget, QListWidgetItem

from app.models import Finding


class FindingList(QListWidget):
    """Lista visual de vestígios técnicos."""

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("FindingList")

    def update_findings(self, findings: list[Finding]) -> None:
        self.clear()

        if not findings:
            self.addItem("Nenhum vestígio técnico identificado.")
            return

        for finding in findings:
            item = QListWidgetItem(
                f"{finding.severity.value.upper()} | {finding.category}\n"
                f"{finding.title}\n"
                f"{finding.description}"
            )

            self.addItem(item)
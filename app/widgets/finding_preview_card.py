from PySide6.QtWidgets import QLabel, QVBoxLayout, QFrame, QWidget

from app.models.analysis_result import Finding


class FindingsPreviewCard(QWidget):
    """Card compacto para mostrar apenas os principais vestígios na aba Geral."""

    def __init__(self) -> None:
        super().__init__()

        self.container = QVBoxLayout()
        self.container.setSpacing(8)

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("findingsPreviewCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(10)

        title = QLabel("🧩 Principais Vestígios")
        title.setObjectName("findingsPreviewTitle")

        subtitle = QLabel("Prévia dos achados mais relevantes. A análise completa fica na aba Vestígios.")
        subtitle.setObjectName("findingsPreviewSubtitle")
        subtitle.setWordWrap(True)

        card_layout.addWidget(title)
        card_layout.addWidget(subtitle)
        card_layout.addLayout(self.container)

        main_layout.addWidget(card)

    def update_findings(self, findings: list[Finding]) -> None:
        self._clear_layout()

        if not findings:
            empty = QLabel("Nenhum vestígio relevante identificado até o momento.")
            empty.setObjectName("findingsPreviewText")
            empty.setWordWrap(True)
            self.container.addWidget(empty)
            return

        for finding in findings[:3]:
            item = QLabel(f"{self._severity_icon(finding)} {finding.title}")
            item.setObjectName("findingsPreviewText")
            item.setWordWrap(True)
            self.container.addWidget(item)

        if len(findings) > 3:
            more = QLabel(f"+ {len(findings) - 3} vestígio(s) disponível(is) na aba Vestígios.")
            more.setObjectName("findingsPreviewMuted")
            self.container.addWidget(more)

    def _severity_icon(self, finding: Finding) -> str:
        severity = getattr(finding.severity, "value", "").lower()

        if severity == "critical":
            return "❌"
        if severity == "warning":
            return "⚠"
        if severity == "success":
            return "✅"
        return "ℹ"

    def _clear_layout(self) -> None:
        while self.container.count():
            item = self.container.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
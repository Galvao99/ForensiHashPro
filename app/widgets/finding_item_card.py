from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.models import Finding


class FindingItemCard(QWidget):
    """Card individual de um vestígio técnico."""

    def __init__(self, finding: Finding) -> None:
        super().__init__()
        self.finding = finding
        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName(self._card_style())

        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)

        header = QHBoxLayout()

        title = QLabel(f"{self._icon()} {self.finding.title}")
        title.setObjectName("findingItemTitle")
        title.setWordWrap(True)

        severity = QLabel(self.finding.severity.value.upper())
        severity.setObjectName(self._severity_badge_style())
        severity.setAlignment(Qt.AlignCenter)

        header.addWidget(title)
        header.addStretch()
        header.addWidget(severity)

        category = QLabel(f"Categoria: {self.finding.category}")
        category.setObjectName("findingItemMuted")

        description = QLabel(self.finding.description)
        description.setObjectName("findingItemText")
        description.setWordWrap(True)

        layout.addLayout(header)
        layout.addWidget(category)
        layout.addWidget(description)

        layout.addWidget(self._line("Fonte", self.finding.evidence_source))
        layout.addWidget(self._line("Valor observado", self.finding.observed_value))
        layout.addWidget(self._line("Valor esperado", self.finding.expected_value))
        layout.addWidget(self._line("Recomendação", self.finding.recommendation))

        score = QLabel(f"Confiança/Peso técnico: {self.finding.score:.0%}")
        score.setObjectName("findingItemMuted")
        layout.addWidget(score)

        main_layout.addWidget(card)

    def _line(self, label: str, value: str | None) -> QLabel:
        text = QLabel(f"{label}: {value or '-'}")
        text.setObjectName("findingItemText")
        text.setWordWrap(True)
        return text

    def _icon(self) -> str:
        severity = self.finding.severity.value.lower()

        if severity == "critical":
            return "❌"
        if severity == "warning":
            return "⚠"
        if severity == "success":
            return "✅"
        return "ℹ"

    def _card_style(self) -> str:
        severity = self.finding.severity.value.lower()

        if severity == "critical":
            return "findingItemCritical"
        if severity == "warning":
            return "findingItemWarning"
        if severity == "success":
            return "findingItemSuccess"
        return "findingItemInfo"

    def _severity_badge_style(self) -> str:
        severity = self.finding.severity.value.lower()
        return f"findingBadge_{severity}"
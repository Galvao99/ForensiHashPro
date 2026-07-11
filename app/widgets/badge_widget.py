from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from app.models.badge import Badge


class BadgeWidget(QLabel):
    """
    Componente visual responsável por renderizar um Badge.
    """

    COLOR_CLASSES = {
        "green": "success",
        "blue": "info",
        "orange": "warning",
        "red": "critical",
        "gray": "neutral",
    }

    def __init__(
        self,
        badge: Badge,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.badge = badge

        self.setObjectName("EvidenceBadge")
        self.setProperty(
            "badgeType",
            self.COLOR_CLASSES.get(
                badge.color.lower(),
                "neutral",
            ),
        )

        self.setText(self._build_text())
        self.setToolTip(badge.tooltip)

        self.setAlignment(Qt.AlignCenter)
        self.setSizePolicy(
            QSizePolicy.Maximum,
            QSizePolicy.Fixed,
        )

        self.setMinimumHeight(25)

    def _build_text(self) -> str:
        if not self.badge.icon:
            return self.badge.text

        icon_map = {
            "check": "✓",
            "warning": "⚠",
            "error": "✕",
            "info": "ℹ",
        }

        icon = icon_map.get(
            self.badge.icon,
            self.badge.icon,
        )

        return f"{icon}  {self.badge.text}"
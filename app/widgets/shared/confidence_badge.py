from PySide6.QtWidgets import QLabel


class ConfidenceBadge(QLabel):
    def __init__(self) -> None:
        super().__init__("0%")
        self.setObjectName("ConfidenceBadge")

    def set_confidence(self, value: int) -> None:
        self.setText(f"{value}%")

        if value >= 90:
            kind = "success"
        elif value >= 60:
            kind = "warning"
        else:
            kind = "danger"

        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
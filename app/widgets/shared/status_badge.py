from PySide6.QtWidgets import QLabel

class StatusBadge(QLabel):
    def __init__(self, text: str = "Status") -> None:
        super().__init__(text)
        self.setObjectName("StatusBadge")

    def set_status(self, text: str, kind: str = "success") -> None:
        self.setText(text)
        self.setProperty("kind", kind)
        self.style().unpolish(self)
        self.style().polish(self)
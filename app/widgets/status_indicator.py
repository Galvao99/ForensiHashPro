from PySide6.QtWidgets import QLabel


class StatusIndicator(QLabel):
    LABELS = {
        "completed": "CONCLUÍDO",
        "partial": "PARCIAL",
        "failed": "FALHOU",
        "skipped": "NÃO EXECUTADO",
        "unavailable": "INDISPONÍVEL",
    }

    def __init__(self, status: str = "unavailable") -> None:
        super().__init__()
        self.setObjectName("StatusIndicator")
        self.set_status(status)

    def set_status(self, status: str) -> None:
        normalized = status if status in self.LABELS else "unavailable"
        self.setProperty("status", normalized)
        self.setText(self.LABELS[normalized])
        self.style().unpolish(self)
        self.style().polish(self)


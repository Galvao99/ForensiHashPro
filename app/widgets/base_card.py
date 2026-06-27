from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class BaseCard(QFrame):
    """Card base reutilizável."""

    def __init__(self, title: str) -> None:
        super().__init__()

        self.setObjectName("BaseCard")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")

        self.body_layout = QVBoxLayout()

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addLayout(self.body_layout)

        self.setLayout(layout)
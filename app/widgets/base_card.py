from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class BaseCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()

        self.setObjectName("BaseCard")

        self.title = QLabel(title)
        self.title.setObjectName("CardTitle")

        self.body_layout = QVBoxLayout()

        layout = QVBoxLayout()
        layout.addWidget(self.title)
        layout.addLayout(self.body_layout)

        self.setLayout(layout)
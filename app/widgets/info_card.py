from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout


class InfoCard(QFrame):
    """Card reutilizável para exibição de informações."""

    def __init__(self, title: str, content: str = "") -> None:
        super().__init__()

        self.setObjectName("InfoCard")

        self.title_label = QLabel(title)
        self.title_label.setObjectName("CardTitle")

        self.content_label = QLabel(content)
        self.content_label.setObjectName("CardContent")
        self.content_label.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(self.title_label)
        layout.addWidget(self.content_label)

        self.setLayout(layout)

    def set_content(self, content: str) -> None:
        self.content_label.setText(content)
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ComparisonPage(QWidget):
    """Página de comparação forense entre arquivos."""

    def __init__(self) -> None:
        super().__init__()

        title = QLabel("Comparação Forense")
        title.setObjectName("PageTitle")

        placeholder = QLabel(
            "Selecione dois arquivos para comparar hashes, magic numbers, "
            "metadados e assinaturas digitais."
        )
        placeholder.setObjectName("CardContent")
        placeholder.setWordWrap(True)

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addWidget(placeholder)
        layout.addStretch()

        self.setLayout(layout)
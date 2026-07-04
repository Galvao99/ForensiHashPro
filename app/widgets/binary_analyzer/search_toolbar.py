from PySide6.QtWidgets import QComboBox, QFrame, QHBoxLayout, QLineEdit, QPushButton


class SearchToolbar(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("SearchToolbar")

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar no binário...")

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Texto", "HEX"])

        self.search_button = QPushButton("Buscar")
        self.export_button = QPushButton("Exportar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        layout.addWidget(self.search_input)
        layout.addWidget(self.mode_combo)
        layout.addWidget(self.search_button)
        layout.addWidget(self.export_button)
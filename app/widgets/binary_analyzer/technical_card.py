from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from app.models import MagicNumberResult


class TechnicalCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BinaryCard")

        self.offset_label = QLabel("-")
        self.size_label = QLabel("-")
        self.encoding_label = QLabel("ASCII")
        self.mime_label = QLabel("-")
        self.corrupted_label = QLabel("-")
        self.ascii_label = QLabel("-")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("⚙️ Informações Técnicas")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setVerticalSpacing(10)
        grid.setHorizontalSpacing(16)

        grid.addWidget(QLabel("Offset inicial:"), 0, 0)
        grid.addWidget(self.offset_label, 0, 1)

        grid.addWidget(QLabel("Tamanho da assinatura:"), 1, 0)
        grid.addWidget(self.size_label, 1, 1)

        grid.addWidget(QLabel("ASCII:"), 2, 0)
        grid.addWidget(self.ascii_label, 2, 1)

        grid.addWidget(QLabel("Encoding:"), 3, 0)
        grid.addWidget(self.encoding_label, 3, 1)

        grid.addWidget(QLabel("MIME:"), 4, 0)
        grid.addWidget(self.mime_label, 4, 1)

        grid.addWidget(QLabel("Arquivo corrompido:"), 5, 0)
        grid.addWidget(self.corrupted_label, 5, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def update_result(self, result: MagicNumberResult) -> None:
        self.offset_label.setText(f"0x{result.offset:08X} ({result.offset})")
        self.size_label.setText(f"{len(result.signature.split())} bytes")
        self.ascii_label.setText(result.ascii_signature or "-")
        self.mime_label.setText(result.mime_type)
        self.corrupted_label.setText(
            "Detectado" if result.is_corrupted else "Não detectado"
        )
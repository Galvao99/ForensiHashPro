from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout

from app.models import MagicNumberResult
from app.widgets.shared.confidence_badge import ConfidenceBadge
from app.widgets.shared.status_badge import StatusBadge


class SummaryCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BinaryCard")

        self.type_label = QLabel("-")
        self.type_label.setObjectName("BigGreenText")

        self.format_label = QLabel("-")
        self.signature_label = QLabel("-")
        self.extension_label = QLabel("-")

        self.confidence_badge = ConfidenceBadge()
        self.status_badge = StatusBadge()

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("🧬 Identificação Binária")
        title.setObjectName("CardTitle")

        layout.addWidget(title)

        layout.addWidget(QLabel("Tipo de arquivo detectado"))
        layout.addWidget(self.type_label)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)

        grid.addWidget(QLabel("Formato:"), 0, 0)
        grid.addWidget(self.format_label, 0, 1)

        grid.addWidget(QLabel("Magic Number:"), 1, 0)
        grid.addWidget(self.signature_label, 1, 1)

        grid.addWidget(QLabel("Extensão:"), 2, 0)
        grid.addWidget(self.extension_label, 2, 1)

        grid.addWidget(QLabel("Confiança:"), 3, 0)
        grid.addWidget(self.confidence_badge, 3, 1)

        grid.addWidget(QLabel("Status:"), 4, 0)
        grid.addWidget(self.status_badge, 4, 1)

        layout.addLayout(grid)
        layout.addStretch()

    def update_result(self, result: MagicNumberResult) -> None:
        self.type_label.setText(result.detected_type)
        self.format_label.setText(result.detected_format)
        self.signature_label.setText(result.signature)
        self.extension_label.setText(result.extension or "(sem extensão)")
        self.confidence_badge.set_confidence(result.confidence)

        if result.is_corrupted:
            self.status_badge.set_status("Possível corrupção", "danger")
        elif result.extension_matches:
            self.status_badge.set_status("Compatível", "success")
        else:
            self.status_badge.set_status("Atenção", "warning")
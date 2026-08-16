from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from app.models import AnalysisResult
from app.processing import ProcessingStatus
from app.widgets.status_indicator import StatusIndicator


class ResultHeader(QFrame):
    """Identidade única do resultado atualmente selecionado."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ResultHeader")

        self.eyebrow = QLabel("RESULTADO TÉCNICO")
        self.eyebrow.setObjectName("ResultEyebrow")
        self.file_name = QLabel("Nenhum arquivo selecionado")
        self.file_name.setObjectName("ResultFileName")
        self.file_name.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status = StatusIndicator()

        title_row = QHBoxLayout()
        title_row.addWidget(self.file_name, stretch=1)
        title_row.addWidget(self.status, alignment=Qt.AlignTop)

        hash_label = QLabel("SHA-256")
        hash_label.setObjectName("TechnicalFieldLabel")
        self.hash_value = QLabel("—")
        self.hash_value.setObjectName("ResultHash")
        self.hash_value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.hash_value.setToolTip("SHA-256 do artefato selecionado")
        self.copy_button = QPushButton("COPIAR")
        self.copy_button.setObjectName("CopyHashButton")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(self.copy_hash)

        hash_row = QHBoxLayout()
        hash_row.setSpacing(10)
        hash_row.addWidget(self.hash_value, stretch=1)
        hash_row.addWidget(self.copy_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 17, 20, 17)
        layout.setSpacing(7)
        layout.addWidget(self.eyebrow)
        layout.addLayout(title_row)
        layout.addSpacing(5)
        layout.addWidget(hash_label)
        layout.addLayout(hash_row)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.file_name.setText(result.file_info.name)
        self.file_name.setToolTip(result.file_info.name)
        digest = result.hashes.sha256 or "—"
        self.hash_value.setText(digest)
        self.hash_value.setToolTip(digest)
        self.copy_button.setEnabled(bool(result.hashes.sha256))
        statuses = {step.status for step in result.processing_steps}
        partial = bool(
            statuses
            & {
                ProcessingStatus.FAILED,
                ProcessingStatus.PARTIAL,
                ProcessingStatus.LIMIT_EXCEEDED,
            }
        )
        self.status.set_status("partial" if partial else "completed")

    def copy_hash(self) -> None:
        if self.hash_value.text() != "—":
            QGuiApplication.clipboard().setText(self.hash_value.text())


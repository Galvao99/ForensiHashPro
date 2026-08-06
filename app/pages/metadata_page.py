from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.metadata_table import MetadataTable


class MetadataPage(QWidget):
    """Página dedicada aos metadados."""

    def __init__(self) -> None:
        super().__init__()

        self.metadata_table = MetadataTable()
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.hide()

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.metadata_table)

        self.setLayout(layout)

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:

        self.metadata_table.update_metadata(
            result.metadata
        )
        step = next(
            (
                item
                for item in getattr(result, "processing_steps", [])
                if item.component == "metadata"
            ),
            None,
        )
        if step is not None and step.status.value not in {"success", "no_findings"}:
            self.status_label.setText(step.user_message)
            self.status_label.show()
        else:
            self.status_label.clear()
            self.status_label.hide()

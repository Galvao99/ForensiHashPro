from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.metadata_table import MetadataTable


class MetadataPage(QWidget):
    """Página dedicada aos metadados."""

    def __init__(self) -> None:
        super().__init__()

        self.metadata_table = MetadataTable()

        layout = QVBoxLayout()
        layout.addWidget(self.metadata_table)

        self.setLayout(layout)

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:

        self.metadata_table.update_metadata(
            result.metadata
        )
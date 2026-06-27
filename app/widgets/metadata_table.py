from PySide6.QtWidgets import QHeaderView, QTableWidget, QTableWidgetItem

from app.models import MetadataResult


class MetadataTable(QTableWidget):
    """Tabela para exibição dos metadados."""

    def __init__(self) -> None:
        super().__init__()

        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["Campo", "Valor"])

        self.horizontalHeader().setStretchLastSection(True)
        self.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeToContents,
        )

        self.setAlternatingRowColors(True)

        self.setEditTriggers(
            QTableWidget.NoEditTriggers
        )

    def update_metadata(
        self,
        metadata: MetadataResult,
    ) -> None:

        self.setRowCount(0)

        for row, (key, value) in enumerate(metadata.raw.items()):

            self.insertRow(row)

            self.setItem(
                row,
                0,
                QTableWidgetItem(str(key)),
            )

            self.setItem(
                row,
                1,
                QTableWidgetItem(str(value)),
            )
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.models import MagicNumberResult


class FindingsTable(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("BinaryCard")

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        title = QLabel("📋 Tabela de Estruturas Encontradas")
        title.setObjectName("CardTitle")
        layout.addWidget(title)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("BinaryTable")
        self.table.setHorizontalHeaderLabels(
            ["#", "Offset", "Hex", "ASCII", "Descrição"]
        )

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)

        layout.addWidget(self.table)

    def update_result(self, result: MagicNumberResult) -> None:
        findings = result.findings or []

        self.table.setRowCount(len(findings))

        for row, finding in enumerate(findings):
            values = [
                str(row + 1),
                f"0x{finding.offset:08X}",
                finding.hex_value,
                finding.ascii_value,
                finding.description,
            ]

            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() ^ Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, col, item)

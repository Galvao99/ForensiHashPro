from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult


class HashPage(QWidget):
    """Página de hashes em formato de tabela, estilo QuickHash."""

    HASH_OPTIONS = {
        "MD5": "md5",
        "SHA-1": "sha1",
        "SHA-224": "sha224",
        "SHA-256": "sha256",
        "SHA-384": "sha384",
        "SHA-512": "sha512",
    }

    def __init__(self) -> None:
        super().__init__()

        self.results: list[AnalysisResult] = []

        self.title = QLabel("🔐 Hashes")
        self.title.setObjectName("SectionTitle")

        self.subtitle = QLabel(
            "Visualize os arquivos analisados e seus respectivos hashes conforme o algoritmo selecionado."
        )
        self.subtitle.setObjectName("SectionSubtitle")

        self.hash_selector = QComboBox()
        self.hash_selector.setObjectName("HashSelector")
        self.hash_selector.addItems(self.HASH_OPTIONS.keys())
        self.hash_selector.setCurrentText("SHA-256")
        self.hash_selector.currentTextChanged.connect(self.refresh_table)

        top_layout = QHBoxLayout()
        top_layout.addWidget(self.subtitle)
        top_layout.addStretch()
        top_layout.addWidget(QLabel("Algoritmo:"))
        top_layout.addWidget(self.hash_selector)

        self.table = QTableWidget()
        self.table.setObjectName("HashTable")
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(
            ["Arquivo", "Extensão", "Tamanho", "Hash"]
        )
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setWordWrap(False)

        self.table.setColumnWidth(0, 260)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 720)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.addWidget(self.title)
        layout.addLayout(top_layout)
        layout.addWidget(self.table)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.results = [result]
        self.refresh_table()

    def update_folder_analysis(self, results: list[AnalysisResult]) -> None:
        self.results = results
        self.refresh_table()

    def refresh_table(self) -> None:
        self.table.setRowCount(0)

        if not self.results:
            return

        selected_label = self.hash_selector.currentText()
        attr_name = self.HASH_OPTIONS.get(selected_label, "sha256")

        self.table.setRowCount(len(self.results))

        for row, result in enumerate(self.results):
            file_name = result.file_info.name
            extension = result.file_info.extension
            size = self._format_size(result.file_info.size_bytes)
            hash_value = getattr(result.hashes, attr_name, "")

            self._set_item(row, 0, file_name)
            self._set_item(row, 1, extension)
            self._set_item(row, 2, size)
            self._set_item(row, 3, hash_value)

        self.table.resizeRowsToContents()

    def _set_item(self, row: int, column: int, text: str) -> None:
        item = QTableWidgetItem(text)
        item.setToolTip(text)
        self.table.setItem(row, column, item)

    def _format_size(self, size_bytes: int) -> str:
        if size_bytes < 1024:
            return f"{size_bytes} B"

        if size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.2f} KB"

        if size_bytes < 1024 * 1024 * 1024:
            return f"{size_bytes / (1024 * 1024):.2f} MB"

        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"
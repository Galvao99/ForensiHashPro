from pathlib import Path

from PySide6.QtWidgets import QListWidget, QListWidgetItem


class FileList(QListWidget):
    """Lista de arquivos carregados na análise."""

    def add_file(self, file_path: Path) -> None:
        item = QListWidgetItem(file_path.name)
        item.setData(1, file_path)
        self.addItem(item)

    def add_files(self, files: list[Path]) -> None:
        self.clear()

        for file_path in files:
            self.add_file(file_path)
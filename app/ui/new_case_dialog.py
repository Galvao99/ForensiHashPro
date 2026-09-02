from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QMessageBox, QPushButton, QVBoxLayout, QWidget,
)


class NewCaseDialog(QDialog):
    """Collects a user-defined case name and inputs; performs no analysis."""

    def __init__(self, parent: QWidget | None = None, paths: list[Path] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Novo Caso")
        self.setObjectName("NewCaseDialog")
        self.setMinimumWidth(520)
        self._paths: list[Path] = []

        layout = QVBoxLayout(self)
        title = QLabel("Novo Caso")
        title.setObjectName("DialogTitle")
        layout.addWidget(title)
        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.setObjectName("CaseNameEdit")
        self.name_edit.setPlaceholderText("Nome definido pelo usuário")
        form.addRow("Nome do Caso", self.name_edit)
        layout.addLayout(form)

        files_label = QLabel("Arquivos")
        files_label.setObjectName("SectionLabel")
        layout.addWidget(files_label)
        self.drop_hint = QLabel("Arraste uma pasta ou arquivos para a Home")
        self.drop_hint.setObjectName("CaseDropHint")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.drop_hint)
        self.path_list = QListWidget()
        self.path_list.setObjectName("CasePathList")
        self.path_list.setMaximumHeight(130)
        layout.addWidget(self.path_list)

        actions = QHBoxLayout()
        folder_button = QPushButton("Selecionar pasta")
        file_button = QPushButton("Selecionar arquivos")
        folder_button.clicked.connect(self._select_folder)
        file_button.clicked.connect(self._select_files)
        actions.addWidget(folder_button)
        actions.addWidget(file_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Criar Caso")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        self.buttons.accepted.connect(self._validate)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.set_paths(paths or [])

    @property
    def case_name(self) -> str:
        return self.name_edit.text().strip()

    @property
    def selected_paths(self) -> list[Path]:
        return list(self._paths)

    def set_paths(self, paths: list[Path]) -> None:
        unique: dict[str, Path] = {}
        for path in paths:
            resolved = path.resolve()
            unique[str(resolved)] = resolved
        self._paths = list(unique.values())
        self.path_list.clear()
        self.path_list.addItems([str(path) for path in self._paths])

    def _select_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "Selecionar pasta")
        if selected:
            self.set_paths([Path(selected)])

    def _select_files(self) -> None:
        selected, _ = QFileDialog.getOpenFileNames(self, "Selecionar arquivos")
        if selected:
            self.set_paths([Path(item) for item in selected])

    def _validate(self) -> None:
        if not self.case_name:
            QMessageBox.warning(self, "Novo Caso", "Informe o nome do Caso.")
            self.name_edit.setFocus()
            return
        if not self._paths:
            QMessageBox.warning(self, "Novo Caso", "Selecione uma pasta ou arquivos.")
            return
        self.accept()

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QButtonGroup, QLabel, QPushButton, QVBoxLayout, QWidget


class SettingsPage(QWidget):
    theme_requested = Signal(str)

    def __init__(self, theme_mode: str = "light") -> None:
        super().__init__()
        self.setObjectName("SettingsPage")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(10)
        title = QLabel("Aparência")
        title.setObjectName("SettingsSectionTitle")
        layout.addWidget(title)
        description = QLabel("Escolha como o ForensiHash apresenta suas superfícies.")
        description.setObjectName("SettingsDescription")
        layout.addWidget(description)
        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)
        self.theme_buttons: dict[str, QPushButton] = {}
        for mode, text in (("light", "Claro"), ("dark", "Escuro"), ("system", "Usar configuração do sistema")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setObjectName("ThemeOptionButton")
            button.clicked.connect(lambda checked, value=mode: checked and self.theme_requested.emit(value))
            self.theme_group.addButton(button)
            self.theme_buttons[mode] = button
            layout.addWidget(button)
        self.set_theme_mode(theme_mode)
        layout.addStretch()

    def set_theme_mode(self, mode: str) -> None:
        self.theme_buttons.get(mode, self.theme_buttons["light"]).setChecked(True)

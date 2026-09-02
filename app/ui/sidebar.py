from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSizePolicy,
    QVBoxLayout, QWidget,
)

from app.settings import ApplicationPaths
from app.ui.line_icons import LineIcon
from app.widgets.file_list import FileList


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    new_case_requested = Signal()
    open_case_requested = Signal()
    collapsed_changed = Signal(bool)

    CASE_ONLY_KEYS = {
        "general", "hashes", "metadata", "findings", "timeline", "magic_number",
        "digital_signature", "integrity", "ocr", "ip", "comparison",
    }
    ITEMS = (
        ("general", "layout-dashboard", "Visão Geral"),
        ("hashes", "hash", "Hashes"),
        ("metadata", "file-info", "Metadados"),
        ("findings", "microscope", "Vestígios técnicos"),
        ("timeline", "clock", "Timeline"),
        ("magic_number", "binary", "Magic Number"),
        ("digital_signature", "signature", "Assinaturas"),
        ("integrity", "shield-check", "Integridade"),
        ("ocr", "text-recognition", "OCR e busca"),
        ("ip", "network", "Contexto de IP"),
        ("comparison", "topology-star", "Correlações"),
    )

    def __init__(self, paths: ApplicationPaths | None = None, theme_mode: str = "light") -> None:
        super().__init__()
        self.paths = paths or ApplicationPaths.discover()
        self.setObjectName("Sidebar")
        self.setFixedWidth(260)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.navigation_buttons: dict[str, QPushButton] = {}
        self.navigation_labels: dict[str, QLabel] = {}
        self._all_buttons: dict[str, QPushButton] = {}
        self._all_labels: dict[str, QLabel] = {}
        self._collapsed = False
        self._case_open = False
        self._build_ui()
        self.set_theme_mode(theme_mode)
        self.set_case(None, 0, None)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 12, 10, 10)
        root.setSpacing(4)
        brand_row = QHBoxLayout()
        self.brand_logo = QLabel()
        self.brand_logo.setObjectName("SidebarBrandLogo")
        self.brand_logo.setAccessibleName("ForensiHash")
        self.brand_logo.setFixedHeight(30)
        self.brand_logo.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.collapse_button = QPushButton()
        self.collapse_button.setObjectName("SidebarCollapseButton")
        self.collapse_button.setFixedSize(32, 30)
        self.collapse_button.setToolTip("Recolher Sidebar")
        self.collapse_button.setAccessibleName("Recolher Sidebar")
        collapse_layout = QHBoxLayout(self.collapse_button)
        collapse_layout.setContentsMargins(7, 0, 7, 0)
        self.collapse_icon = LineIcon(
            "layout-sidebar-left-collapse", self.collapse_button, 17, paths=self.paths
        )
        self.expand_icon = LineIcon(
            "layout-sidebar-left-expand", self.collapse_button, 17, paths=self.paths
        )
        self.expand_icon.setVisible(False)
        collapse_layout.addWidget(self.collapse_icon)
        collapse_layout.addWidget(self.expand_icon)
        self.collapse_button.clicked.connect(self.toggle_collapsed)
        brand_row.addWidget(self.brand_logo, stretch=1)
        brand_row.addWidget(self.collapse_button)
        root.addLayout(brand_row)
        root.addSpacing(10)

        self.navigation_group = QButtonGroup(self)
        self.navigation_group.setExclusive(True)
        self.home_button = self._nav("home", "home", "Home", tracked=False)
        root.addWidget(self.home_button)
        self.new_case_button = self._nav("new_case", "briefcase", "Novo Caso", tracked=False, checkable=False)
        self.open_case_button = self._nav("open_case", "file", "Abrir Caso", tracked=False, checkable=False)
        self.open_file_button = self._nav("open_file", "file", "Selecionar arquivos", tracked=False, checkable=False)
        self.open_folder_button = self._nav("open_folder", "briefcase", "Selecionar pasta", tracked=False, checkable=False)
        self.new_case_button.clicked.connect(self.new_case_requested.emit)
        self.open_case_button.clicked.connect(self.open_case_requested.emit)
        root.addWidget(self.new_case_button)
        root.addWidget(self.open_case_button)

        self.case_section = QWidget()
        case_layout = QVBoxLayout(self.case_section)
        case_layout.setContentsMargins(0, 9, 0, 0)
        case_layout.setSpacing(3)
        self.case_group_label = self._section("CASO ATUAL")
        case_layout.addWidget(self.case_group_label)
        self.case_name_label = QLabel()
        self.case_name_label.setObjectName("SidebarCaseName")
        self.case_name_label.setWordWrap(True)
        self.case_details_label = QLabel()
        self.case_details_label.setObjectName("SidebarCaseDetails")
        case_layout.addWidget(self.case_name_label)
        case_layout.addWidget(self.case_details_label)
        self.file_panel = self._file_panel()
        case_layout.addWidget(self.file_panel)
        for key, icon, label in self.ITEMS:
            case_layout.addWidget(self._nav(key, icon, label))
        root.addWidget(self.case_section, stretch=1)

        self.no_case_spacer = QWidget()
        root.addWidget(self.no_case_spacer, stretch=1)
        self.tools_label = self._section("FERRAMENTAS")
        root.addWidget(self.tools_label)
        root.addWidget(self._nav("deep_file_explorer", "file-search", "Deep File Explorer"))
        root.addWidget(self._separator())
        self.diagnostics_button = self._nav("diagnostics", "activity", "Diagnóstico", tracked=False)
        self.settings_button = self._nav("settings", "settings", "Configurações", tracked=False)
        root.addWidget(self.diagnostics_button)
        root.addWidget(self.settings_button)

        self.export_button = self._nav("export", "file", "Exportar", tracked=False, checkable=False)
        self.export_button.setVisible(False)
        self.legacy_overview_label = QLabel("Visão geral", self)
        self.legacy_overview_label.setVisible(False)

    def _file_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 4, 0, 5)
        layout.setSpacing(4)
        self.file_search = QLineEdit()
        self.file_search.setPlaceholderText("Pesquisar arquivo…")
        self.file_list = FileList()
        self.file_list.setMinimumHeight(80)
        self.file_list.setMaximumHeight(110)
        self.file_search.textChanged.connect(self.file_list.filter_files)
        self.file_count_label = QLabel("0")
        self.file_list.file_count_changed.connect(self._update_file_count)
        layout.addWidget(self.file_search)
        layout.addWidget(self.file_list)
        return panel

    def _nav(
        self, key: str, icon_name: str, text: str, *, tracked: bool = True,
        checkable: bool = True,
    ) -> QPushButton:
        button = QPushButton()
        button.setObjectName("SidebarNavigationButton" if checkable else "SidebarActionButton")
        button.setProperty("pageKey", key)
        button.setCheckable(checkable)
        button.setToolTip(text)
        button.setAccessibleName(text)
        row = QHBoxLayout(button)
        row.setContentsMargins(9, 0, 9, 0)
        row.setSpacing(9)
        icon = LineIcon(icon_name, button)
        icon.setObjectName("SidebarItemIcon")
        icon.setFixedWidth(20)
        label = QLabel(text, button)
        label.setObjectName("SidebarNavigationText")
        label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row.addWidget(icon)
        row.addWidget(label, stretch=1)
        if checkable:
            button.clicked.connect(
                lambda checked=False, page=key: checked and self.navigation_requested.emit(page)
            )
            self.navigation_group.addButton(button)
        self._all_buttons[key] = button
        self._all_labels[key] = label
        if tracked:
            self.navigation_buttons[key] = button
            self.navigation_labels[key] = label
        return button

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SidebarSectionTitle")
        return label

    @staticmethod
    def _separator() -> QFrame:
        frame = QFrame()
        frame.setObjectName("SidebarSeparator")
        frame.setFrameShape(QFrame.Shape.HLine)
        return frame

    def set_theme_mode(self, mode: str) -> None:
        dark = mode == "dark"
        filename = "forensihash_logo_branco.png" if dark else "forensihash_logo_preto.png"
        path = self.paths.resource(f"app/ui/assets/{filename}")
        if path.is_file():
            pixmap = QPixmap(str(path))
            self.brand_logo.setPixmap(
                pixmap.scaled(172, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            self.brand_logo.setText("")
        else:
            self.brand_logo.setPixmap(QPixmap())
            self.brand_logo.setText("ForensiHash")

    def _update_file_count(self, count: int) -> None:
        self.file_count_label.setText(str(count))
        self.file_search.clear()
        if self._case_open:
            self.case_details_label.setText(f"{count} arquivo(s)")

    def set_case(self, name: str | None, file_count: int, state: str | None) -> None:
        self._case_open = bool(name)
        if name:
            self.case_name_label.setText(name)
            detail = f"{file_count} arquivo(s)"
            self.case_details_label.setText(f"{detail} · {state}" if state else detail)
        self._apply_visibility()

    @property
    def is_collapsed(self) -> bool:
        return self._collapsed

    def toggle_collapsed(self) -> None:
        self.set_collapsed(not self._collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if self._collapsed == collapsed:
            return
        self._collapsed = collapsed
        self.setFixedWidth(64 if collapsed else 260)
        self.collapse_icon.setVisible(not collapsed)
        self.expand_icon.setVisible(collapsed)
        self.collapse_button.setToolTip("Expandir Sidebar" if collapsed else "Recolher Sidebar")
        self.collapse_button.setAccessibleName(self.collapse_button.toolTip())
        self._apply_visibility()
        self.collapsed_changed.emit(collapsed)

    def _apply_visibility(self) -> None:
        compact = self._collapsed
        self.brand_logo.setVisible(not compact)
        for label in self._all_labels.values():
            label.setVisible(not compact)
        self.case_group_label.setVisible(self._case_open and not compact)
        self.case_name_label.setVisible(self._case_open and not compact)
        self.case_details_label.setVisible(self._case_open and not compact)
        self.file_panel.setVisible(self._case_open and not compact)
        self.case_section.setVisible(self._case_open or compact)
        self.no_case_spacer.setVisible(not self._case_open and not compact)
        self.new_case_button.setVisible(not self._case_open)
        self.open_case_button.setVisible(not self._case_open)
        self.tools_label.setVisible(not compact)
        for key in self.CASE_ONLY_KEYS:
            self.navigation_buttons[key].setVisible(self._case_open or compact)

    def set_active_page(self, page_key: str | None) -> None:
        self.navigation_group.setExclusive(False)
        for key, button in self._all_buttons.items():
            if button.isCheckable():
                button.setChecked(key == page_key)
        self.navigation_group.setExclusive(True)

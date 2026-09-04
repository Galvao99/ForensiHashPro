from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)

from app.settings import ApplicationPaths
from app.ui.line_icons import LineIcon


class Sidebar(QFrame):
    navigation_requested = Signal(str)
    new_case_requested = Signal()
    open_case_requested = Signal()
    collapsed_changed = Signal(bool)
    group_state_changed = Signal(str, bool)

    CASE_ONLY_KEYS = {
        "general", "hashes", "metadata", "findings", "timeline", "magic_number",
        "digital_signature", "integrity", "ocr", "ip", "correlations", "comparison",
    }
    GROUPS = (
        ("case", "CASO", (
            ("general", "layout-dashboard", "Visão geral"),
            ("timeline", "clock", "Timeline"),
            ("correlations", "topology-star", "Correlações"),
            ("comparison", "file-search", "Comparação"),
        )),
        ("file", "ARQUIVO", (
        ("hashes", "hash", "Hashes"),
        ("metadata", "file-info", "Metadados"),
        ("findings", "microscope", "Vestígios técnicos"),
        ("magic_number", "binary", "Magic Number"),
        ("digital_signature", "signature", "Assinaturas"),
        ("integrity", "shield-check", "Integridade"),
        ("ocr", "text-recognition", "OCR e busca"),
        ("ip", "network", "Contexto de IP"),
        )),
        ("tools", "FERRAMENTAS", (
            ("deep_file_explorer", "file-search", "Deep File Explorer"),
        )),
    )

    def __init__(
        self, paths: ApplicationPaths | None = None, theme_mode: str = "light",
        group_states: dict[str, bool] | None = None,
    ) -> None:
        super().__init__()
        self.paths = paths or ApplicationPaths.discover()
        self.setObjectName("Sidebar")
        self.setFixedWidth(280)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self.navigation_buttons: dict[str, QPushButton] = {}
        self.navigation_labels: dict[str, QLabel] = {}
        self._all_buttons: dict[str, QPushButton] = {}
        self._all_labels: dict[str, QLabel] = {}
        self._collapsed = False
        self._case_open = False
        self.group_buttons: dict[str, QPushButton] = {}
        self.group_containers: dict[str, QWidget] = {}
        self._group_states = {"case": True, "file": True, "tools": True}
        self._group_states.update(group_states or {})
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
        self.brand_logo.setFixedHeight(56)
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
        root.addSpacing(14)

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
        self.case_name_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.case_details_label = QLabel()
        self.case_details_label.setObjectName("SidebarCaseDetails")
        self.case_details_label.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        case_layout.addWidget(self.case_name_label)
        case_layout.addWidget(self.case_details_label)
        for group_key, title, items in self.GROUPS[:2]:
            case_layout.addSpacing(7)
            header, container = self._navigation_group(group_key, title, items)
            case_layout.addWidget(header)
            case_layout.addWidget(container)
        case_layout.addSpacing(7)
        self.tools_label, tools = self._navigation_group(*self.GROUPS[2])
        case_layout.addWidget(self.tools_label)
        case_layout.addWidget(tools)
        case_layout.addStretch()
        self.case_scroll = QScrollArea()
        self.case_scroll.setObjectName("SidebarCaseScroll")
        self.case_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.case_scroll.setWidgetResizable(True)
        self.case_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.case_scroll.setWidget(self.case_section)
        root.addWidget(self.case_scroll, stretch=1)

        root.addWidget(self._separator())
        self.diagnostics_button = self._nav("diagnostics", "activity", "Diagnóstico", tracked=False)
        self.settings_button = self._nav("settings", "settings", "Configurações", tracked=False)
        root.addWidget(self.diagnostics_button)
        root.addWidget(self.settings_button)

        self.export_button = self._nav("export", "file", "Exportar", tracked=False, checkable=False)
        self.export_button.setVisible(False)
        self.legacy_overview_label = QLabel("Visão geral", self)
        self.legacy_overview_label.setVisible(False)

    def _navigation_group(self, key: str, title: str, items: tuple) -> tuple[QPushButton, QWidget]:
        header = QPushButton()
        header.setObjectName("SidebarGroupButton")
        header.setAccessibleName(f"{title}: expandir ou recolher")
        header.setToolTip(title.title())
        row = QHBoxLayout(header)
        row.setContentsMargins(8, 0, 7, 0)
        label = QLabel(title)
        label.setObjectName("SidebarSectionTitle")
        indicator = QLabel("▾" if self._group_states[key] else "▸")
        indicator.setObjectName("SidebarGroupIndicator")
        row.addWidget(label, stretch=1)
        row.addWidget(indicator)
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        for page_key, icon, text in items:
            layout.addWidget(self._nav(page_key, icon, text))
        container.setVisible(self._group_states[key])
        header.clicked.connect(lambda _=False, group=key: self.set_group_expanded(group, not self._group_states[group]))
        header.setProperty("indicator", indicator)
        self.group_buttons[key] = header
        self.group_containers[key] = container
        return header, container

    def set_group_expanded(self, group: str, expanded: bool) -> None:
        if group not in self.group_containers or self._group_states[group] == expanded:
            return
        self._group_states[group] = expanded
        self.group_containers[group].setVisible(expanded and not self._collapsed)
        indicator = self.group_buttons[group].property("indicator")
        if isinstance(indicator, QLabel):
            indicator.setText("▾" if expanded else "▸")
        self.group_state_changed.emit(group, expanded)

    def group_expanded(self, group: str) -> bool:
        return self._group_states[group]

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
                pixmap.scaled(225, 54, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
            self.brand_logo.setText("")
        else:
            self.brand_logo.setPixmap(QPixmap())
            self.brand_logo.setText("ForensiHash")

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
        self.setFixedWidth(64 if collapsed else 280)
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
        self.case_section.setVisible(True)
        self.case_scroll.setVisible(True)
        self.new_case_button.setVisible(not self._case_open)
        self.open_case_button.setVisible(not self._case_open)
        self.tools_label.setVisible(not compact)
        for group, header in self.group_buttons.items():
            header.setVisible(not compact and (group == "tools" or self._case_open))
            self.group_containers[group].setVisible(
                (self._case_open or group == "tools" or compact)
                and (compact or self._group_states[group])
            )
        for key in self.CASE_ONLY_KEYS:
            self.navigation_buttons[key].setVisible(self._case_open or compact)

    def set_active_page(self, page_key: str | None) -> None:
        self.navigation_group.setExclusive(False)
        for key, button in self._all_buttons.items():
            if button.isCheckable():
                button.setChecked(key == page_key)
        self.navigation_group.setExclusive(True)

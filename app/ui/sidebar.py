from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.widgets.file_list import FileList


class Sidebar(QFrame):
    """
    Barra lateral com ações, explorador e navegação técnica.
    """

    navigation_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("Sidebar")
        self.setMinimumWidth(250)
        self.setMaximumWidth(310)

        self.navigation_buttons: dict[
            str,
            QPushButton,
        ] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            14,
            18,
            14,
            16,
        )
        root_layout.setSpacing(10)

        root_layout.addWidget(
            self._build_brand()
        )

        root_layout.addSpacing(10)

        root_layout.addWidget(
            self._create_section_title(
                "CASO"
            )
        )

        self.open_file_button = (
            self._create_action_button(
                "▣",
                "Abrir arquivo",
            )
        )

        self.open_folder_button = (
            self._create_action_button(
                "▰",
                "Abrir pasta",
            )
        )

        root_layout.addWidget(
            self.open_file_button
        )
        root_layout.addWidget(
            self.open_folder_button
        )

        root_layout.addWidget(
            self._create_separator()
        )

        root_layout.addWidget(
            self._create_section_title(
                "ARQUIVOS"
            )
        )

        self.file_list = FileList()
        self.file_list.setObjectName(
            "SidebarFileList"
        )
        self.file_list.setMinimumHeight(150)
        self.file_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        root_layout.addWidget(
            self.file_list,
            stretch=1,
        )

        root_layout.addWidget(
            self._create_separator()
        )

        navigation_scroll = QScrollArea()
        navigation_scroll.setObjectName(
            "SidebarNavigationScroll"
        )
        navigation_scroll.setWidgetResizable(True)
        navigation_scroll.setFrameShape(
            QFrame.NoFrame
        )

        navigation_container = QWidget()
        navigation_container.setObjectName(
            "SidebarNavigationContainer"
        )

        navigation_layout = QVBoxLayout(
            navigation_container
        )
        navigation_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        navigation_layout.setSpacing(5)

        navigation_layout.addWidget(
            self._create_section_title(
                "ANÁLISE"
            )
        )

        self.navigation_group = QButtonGroup(
            self
        )
        self.navigation_group.setExclusive(True)

        navigation_items = (
            ("general", "⌂", "Geral"),
            ("hashes", "#", "Hashes"),
            ("metadata", "≡", "Metadados"),
            ("findings", "⌕", "Vestígios"),
            ("timeline", "◷", "Timeline"),
            (
                "magic_number",
                "01",
                "Magic Number",
            ),
            (
                "digital_signature",
                "✓",
                "Assinatura digital",
            ),
            (
                "integrity",
                "◇",
                "Integridade",
            ),
            ("ocr", "T", "OCR e busca"),
            ("ip", "◎", "Contexto de IP"),
            (
                "comparison",
                "⇄",
                "Comparação",
            ),
        )

        for key, icon, text in navigation_items:
            button = self._create_navigation_button(
                key=key,
                icon=icon,
                text=text,
            )

            navigation_layout.addWidget(button)

        navigation_layout.addStretch()

        navigation_scroll.setWidget(
            navigation_container
        )

        root_layout.addWidget(
            navigation_scroll
        )

        root_layout.addWidget(
            self._create_separator()
        )

        root_layout.addWidget(
            self._create_section_title(
                "FERRAMENTAS"
            )
        )

        self.snapshot_button = (
            self._create_action_button(
                "▧",
                "Snapshot",
            )
        )

        self.export_button = (
            self._create_action_button(
                "⇧",
                "Exportar",
            )
        )

        root_layout.addWidget(
            self.snapshot_button
        )
        root_layout.addWidget(
            self.export_button
        )

    def _build_brand(self) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(1)

        title = QLabel("ForensiHash")
        title.setObjectName("SidebarTitle")

        subtitle = QLabel("PRO")
        subtitle.setObjectName(
            "SidebarSubtitle"
        )

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return container

    def _create_section_title(
        self,
        text: str,
    ) -> QLabel:
        label = QLabel(text)
        label.setObjectName(
            "SidebarSectionTitle"
        )

        return label

    def _create_action_button(
        self,
        icon: str,
        text: str,
    ) -> QPushButton:
        button = QPushButton(
            f"{icon}   {text}"
        )
        button.setObjectName(
            "SidebarActionButton"
        )

        return button

    def _create_navigation_button(
        self,
        *,
        key: str,
        icon: str,
        text: str,
    ) -> QPushButton:
        button = QPushButton()

        button.setObjectName(
            "SidebarNavigationButton"
        )

        button.setCheckable(True)

        layout = QHBoxLayout(button)
        layout.setContentsMargins(
            12,
            7,
            10,
            7,
        )
        layout.setSpacing(10)

        icon_label = QLabel(icon)
        icon_label.setObjectName(
            "SidebarNavigationIcon"
        )
        icon_label.setFixedWidth(22)

        text_label = QLabel(text)
        text_label.setObjectName(
            "SidebarNavigationText"
        )

        layout.addWidget(icon_label)
        layout.addWidget(text_label)
        layout.addStretch()

        button.clicked.connect(
            lambda checked,
            page_key=key: (
                self.navigation_requested.emit(
                    page_key
                )
                if checked
                else None
            )
        )

        self.navigation_group.addButton(
            button
        )

        self.navigation_buttons[key] = button

        return button

    def _create_separator(self) -> QFrame:
        separator = QFrame()
        separator.setObjectName(
            "SidebarSeparator"
        )
        separator.setFrameShape(
            QFrame.HLine
        )

        return separator

    def set_active_page(
        self,
        page_key: str | None,
    ) -> None:
        if page_key is None:
            self.navigation_group.setExclusive(
                False
            )

            for button in (
                self.navigation_buttons.values()
            ):
                button.setChecked(False)

            self.navigation_group.setExclusive(
                True
            )

            return

        button = self.navigation_buttons.get(
            page_key
        )

        if button is not None:
            button.setChecked(True)
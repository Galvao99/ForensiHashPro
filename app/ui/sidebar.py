from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.widgets.file_list import FileList
from app.ui.theme import DARK_THEME, brand_logo_path


class Sidebar(QFrame):
    """
    Barra lateral principal do ForensiHash.

    Contém:
    - identidade visual;
    - abertura de arquivos e pastas;
    - navegador de arquivos;
    - navegação entre páginas técnicas;
    - ferramenta de exportação.
    """

    navigation_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("Sidebar")

        # Impede que a sidebar fique pequena demais.
        self.setMinimumWidth(260)

        # Não há largura máxima.
        # O QSplitter principal controlará seu tamanho.
        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Expanding,
        )

        self.navigation_buttons: dict[
            str,
            QPushButton,
        ] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """
        Constrói toda a estrutura visual da sidebar.
        """

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
                "FILE",
                "Abrir arquivo",
            )
        )

        self.open_folder_button = (
            self._create_action_button(
                "DIR",
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

        # Divide verticalmente o navegador de arquivos
        # e o menu das análises.
        self.content_splitter = QSplitter(
            Qt.Vertical
        )

        self.content_splitter.setObjectName(
            "SidebarContentSplitter"
        )

        self.content_splitter.setChildrenCollapsible(
            False
        )

        self.file_panel = (
            self._build_file_panel()
        )

        self.navigation_panel = (
            self._build_navigation_panel()
        )

        self.content_splitter.addWidget(
            self.file_panel
        )

        self.content_splitter.addWidget(
            self.navigation_panel
        )

        # Ambas as áreas podem crescer.
        self.content_splitter.setStretchFactor(
            0,
            1,
        )

        self.content_splitter.setStretchFactor(
            1,
            1,
        )

        # Tamanho inicial aproximado.
        self.content_splitter.setSizes(
            [330, 320]
        )

        root_layout.addWidget(
            self.content_splitter,
            stretch=1,
        )

        root_layout.addWidget(
            self._create_separator()
        )

        root_layout.addWidget(
            self._create_section_title(
                "FERRAMENTAS"
            )
        )

        self.export_button = (
            self._create_action_button(
                "EXP",
                "Exportar",
            )
        )

        root_layout.addWidget(
            self.export_button
        )

    def _build_brand(self) -> QWidget:
        """
        Cria o bloco da marca.
        """

        container = QWidget()
        container.setObjectName(
            "SidebarBrand"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            4,
            0,
            4,
            0,
        )
        layout.setSpacing(1)

        self.brand_logo = QLabel()
        logo_path = brand_logo_path(DARK_THEME)
        if logo_path is not None:
            pixmap = QPixmap(str(logo_path))
            self.brand_logo.setPixmap(
                pixmap.scaled(178, 38, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.brand_logo.setAccessibleName("ForensiHash")
        else:
            self.brand_logo.setText("FORENSIHASH")
            self.brand_logo.setObjectName("SidebarLogoFallback")

        subtitle = QLabel("WORKSTATION PERICIAL LOCAL")
        subtitle.setObjectName("SidebarProductKind")

        layout.addWidget(self.brand_logo)
        layout.addWidget(subtitle)

        return container

    def _build_file_panel(self) -> QWidget:
        """
        Cria o navegador de arquivos.
        """

        panel = QWidget()
        panel.setObjectName(
            "SidebarFilePanel"
        )

        panel.setMinimumHeight(150)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(8)

        layout.addWidget(
            self._build_file_section_header()
        )

        self.file_search = QLineEdit()
        self.file_search.setObjectName(
            "SidebarFileSearch"
        )
        self.file_search.setPlaceholderText(
            "Pesquisar arquivo..."
        )
        self.file_search.setClearButtonEnabled(
            True
        )

        layout.addWidget(
            self.file_search
        )

        self.file_list = FileList()
        self.file_list.setMinimumHeight(
            90
        )
        self.file_list.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Expanding,
        )

        layout.addWidget(
            self.file_list,
            stretch=1,
        )

        self.file_search.textChanged.connect(
            self.file_list.filter_files
        )

        self.file_list.file_count_changed.connect(
            self._update_file_count
        )

        return panel

    def _build_navigation_panel(
        self,
    ) -> QWidget:
        """
        Cria o painel de navegação das análises.
        """

        panel = QWidget()
        panel.setObjectName(
            "SidebarAnalysisPanel"
        )

        panel.setMinimumHeight(180)

        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        panel_layout.setSpacing(6)

        panel_layout.addWidget(
            self._create_section_title(
                "ANÁLISE"
            )
        )

        navigation_scroll = QScrollArea()
        navigation_scroll.setObjectName(
            "SidebarNavigationScroll"
        )
        navigation_scroll.setWidgetResizable(
            True
        )
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
            4,
            0,
        )
        navigation_layout.setSpacing(3)

        self.navigation_group = QButtonGroup(
            self
        )
        self.navigation_group.setExclusive(
            True
        )

        navigation_items = (
            ("general", "SUM", "Visão geral"),
            ("hashes", "HASH", "Hashes"),
            ("metadata", "META", "Metadados"),
            ("findings", "FIND", "Vestígios técnicos"),
            ("timeline", "TIME", "Timeline"),
            (
                "magic_number",
                "MAG",
                "Magic Number",
            ),
            (
                "digital_signature",
                "SIGN",
                "Assinaturas",
            ),
            (
                "integrity",
                "INT",
                "Integridade",
            ),
            (
                "ocr",
                "OCR",
                "OCR e busca",
            ),
            (
                "ip",
                "IP",
                "Contexto de IP",
            ),
            (
                "comparison",
                "CMP",
                "Comparação",
            ),
        )

        for key, icon, text in navigation_items:
            button = (
                self._create_navigation_button(
                    key=key,
                    icon=icon,
                    text=text,
                )
            )

            navigation_layout.addWidget(
                button
            )

        navigation_layout.addStretch()

        navigation_scroll.setWidget(
            navigation_container
        )

        panel_layout.addWidget(
            navigation_scroll,
            stretch=1,
        )

        return panel

    def _build_file_section_header(
        self,
    ) -> QWidget:
        """
        Cria o cabeçalho da lista de arquivos.
        """

        container = QWidget()
        container.setObjectName(
            "SidebarFileHeader"
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            4,
            0,
            4,
            0,
        )
        layout.setSpacing(8)

        title = self._create_section_title(
            "ARQUIVOS"
        )

        self.file_count_label = QLabel("0")
        self.file_count_label.setObjectName(
            "SidebarFileCount"
        )
        self.file_count_label.setAlignment(
            Qt.AlignCenter
        )

        layout.addWidget(title)
        layout.addStretch()
        layout.addWidget(
            self.file_count_label
        )

        return container

    def _update_file_count(
        self,
        count: int,
    ) -> None:
        """
        Atualiza o contador da lista.
        """

        self.file_count_label.setText(
            str(count)
        )

        self.file_search.clear()

    def _create_section_title(
        self,
        text: str,
    ) -> QLabel:
        """
        Cria o título de uma seção.
        """

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
        """
        Cria um botão principal da sidebar.
        """

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
        """
        Cria um botão de navegação técnica.
        """

        button = QPushButton()
        button.setObjectName(
            "SidebarNavigationButton"
        )
        button.setCheckable(True)

        layout = QHBoxLayout(button)
        layout.setContentsMargins(
            10,
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

        self.navigation_buttons[key] = (
            button
        )

        return button

    def _create_separator(self) -> QFrame:
        """
        Cria uma linha separadora.
        """

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
        """
        Define o botão selecionado.
        """

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

from collections import defaultdict
from typing import Literal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult


HashFilter = Literal[
    "all",
    "unique",
    "duplicates",
    "groups",
]


class HashSummaryButton(QPushButton):
    """
    Card clicável utilizado como resumo e filtro
    da página de hashes.
    """

    def __init__(
        self,
        *,
        icon: str,
        title: str,
        card_type: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("HashSummaryButton")
        self.setProperty("cardType", card_type)

        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setText("")

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(
            15,
            12,
            15,
            12,
        )
        root_layout.setSpacing(12)

        self.icon_label = QLabel(icon)
        self.icon_label.setObjectName(
            "HashSummaryIcon"
        )
        self.icon_label.setProperty(
            "cardType",
            card_type,
        )
        self.icon_label.setAlignment(
            Qt.AlignCenter
        )
        self.icon_label.setFixedSize(
            38,
            38,
        )

        information_layout = QVBoxLayout()
        information_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        information_layout.setSpacing(1)

        self.value_label = QLabel("0")
        self.value_label.setObjectName(
            "HashSummaryValue"
        )
        self.value_label.setProperty(
            "cardType",
            card_type,
        )

        self.title_label = QLabel(title)
        self.title_label.setObjectName(
            "HashSummaryTitle"
        )

        information_layout.addWidget(
            self.value_label
        )
        information_layout.addWidget(
            self.title_label
        )

        root_layout.addWidget(
            self.icon_label
        )
        root_layout.addLayout(
            information_layout,
            stretch=1,
        )

    def set_value(
        self,
        value: int,
    ) -> None:
        """
        Atualiza o número principal do card.
        """

        self.value_label.setText(
            str(value)
        )


class HashPage(QWidget):
    """
    Página de análise e comparação de hashes.

    Permite:
    - visualizar todos os arquivos;
    - filtrar arquivos únicos;
    - filtrar arquivos duplicados;
    - visualizar grupos de hashes duplicados;
    - trocar o algoritmo utilizado;
    - ajustar manualmente as colunas;
    - restaurar o dimensionamento automático;
    - reorganizar os cards conforme a largura disponível.
    """

    HASH_OPTIONS = {
        "MD5": "md5",
        "SHA-1": "sha1",
        "SHA-224": "sha224",
        "SHA-256": "sha256",
        "SHA-384": "sha384",
        "SHA-512": "sha512",
    }

    FILTER_ALL: HashFilter = "all"
    FILTER_UNIQUE: HashFilter = "unique"
    FILTER_DUPLICATES: HashFilter = "duplicates"
    FILTER_GROUPS: HashFilter = "groups"

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("HashPage")

        self.results: list[AnalysisResult] = []

        self.current_filter: HashFilter = (
            self.FILTER_ALL
        )

        self.summary_column_count = 0
        self.user_resized_hash_columns = False

        self._build_ui()
        self._connect_signals()

        self.refresh_page()

    def _build_ui(self) -> None:
        """
        Constrói todos os componentes visuais da página.
        """

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        root_layout.setSpacing(14)

        root_layout.addWidget(
            self._build_header()
        )

        root_layout.addLayout(
            self._build_summary_cards()
        )

        root_layout.addWidget(
            self._build_algorithm_toolbar()
        )

        self.table_title = QLabel(
            "Todos os arquivos analisados"
        )
        self.table_title.setObjectName(
            "HashTableTitle"
        )

        root_layout.addWidget(
            self.table_title
        )

        root_layout.addWidget(
            self._build_table(),
            stretch=1,
        )

        self.empty_label = QLabel(
            "Nenhum arquivo corresponde ao filtro selecionado."
        )
        self.empty_label.setObjectName(
            "HashEmptyLabel"
        )
        self.empty_label.setAlignment(
            Qt.AlignCenter
        )
        self.empty_label.setVisible(False)

        root_layout.addWidget(
            self.empty_label
        )

    def _build_header(self) -> QWidget:
        """
        Cria o título e o subtítulo da página.
        """

        container = QWidget()
        container.setObjectName(
            "HashHeader"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        layout.setSpacing(4)

        title = QLabel("Hashes")
        title.setObjectName(
            "SectionTitle"
        )

        subtitle = QLabel(
            "Identifique arquivos com conteúdo binário "
            "idêntico utilizando o algoritmo selecionado."
        )
        subtitle.setObjectName(
            "SectionSubtitle"
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        return container

    def _build_summary_cards(
        self,
    ) -> QGridLayout:
        """
        Cria os quatro cards clicáveis.

        O grid será reorganizado automaticamente:
        - espaço grande: quatro cards;
        - espaço médio: dois cards por linha;
        - espaço reduzido: um card por linha.
        """

        self.summary_layout = QGridLayout()
        self.summary_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self.summary_layout.setHorizontalSpacing(
            10
        )
        self.summary_layout.setVerticalSpacing(
            10
        )

        self.summary_group = QButtonGroup(
            self
        )
        self.summary_group.setExclusive(
            True
        )

        self.total_card = (
            self._create_summary_button(
                icon="▤",
                title="Arquivos",
                card_type="total",
                filter_value=self.FILTER_ALL,
            )
        )

        self.unique_card = (
            self._create_summary_button(
                icon="✓",
                title="Únicos",
                card_type="unique",
                filter_value=self.FILTER_UNIQUE,
            )
        )

        self.duplicate_card = (
            self._create_summary_button(
                icon="≡",
                title="Duplicados",
                card_type="duplicate",
                filter_value=(
                    self.FILTER_DUPLICATES
                ),
            )
        )

        self.group_card = (
            self._create_summary_button(
                icon="⊞",
                title="Grupos",
                card_type="groups",
                filter_value=self.FILTER_GROUPS,
            )
        )

        self.summary_cards = [
            self.total_card,
            self.unique_card,
            self.duplicate_card,
            self.group_card,
        ]

        self.total_card.setChecked(True)

        self._reorganize_summary_cards(
            columns=4
        )

        return self.summary_layout

    def _create_summary_button(
        self,
        *,
        icon: str,
        title: str,
        card_type: str,
        filter_value: HashFilter,
    ) -> HashSummaryButton:
        """
        Cria um card e conecta seu clique ao filtro.
        """

        button = HashSummaryButton(
            icon=icon,
            title=title,
            card_type=card_type,
        )

        button.setProperty(
            "filterValue",
            filter_value,
        )

        button.clicked.connect(
            lambda checked,
            selected_filter=filter_value: (
                self._set_filter(
                    selected_filter
                )
                if checked
                else None
            )
        )

        self.summary_group.addButton(
            button
        )

        return button

    def _build_algorithm_toolbar(
        self,
    ) -> QWidget:
        """
        Cria a barra de opções da página.
        """

        toolbar = QFrame()
        toolbar.setObjectName(
            "HashToolbar"
        )

        layout = QHBoxLayout(toolbar)
        layout.setContentsMargins(
            12,
            8,
            12,
            8,
        )
        layout.setSpacing(8)

        self.toolbar_information = QLabel(
            "A identificação de duplicidade considera "
            "o algoritmo atualmente selecionado."
        )
        self.toolbar_information.setObjectName(
            "HashToolbarInformation"
        )
        self.toolbar_information.setWordWrap(
            True
        )

        self.reset_columns_button = QPushButton(
            "Ajustar colunas"
        )
        self.reset_columns_button.setObjectName(
            "HashResetColumnsButton"
        )
        self.reset_columns_button.setCursor(
            Qt.PointingHandCursor
        )
        self.reset_columns_button.clicked.connect(
            self.reset_table_columns
        )

        algorithm_label = QLabel(
            "Algoritmo:"
        )
        algorithm_label.setObjectName(
            "HashToolbarLabel"
        )

        self.hash_selector = QComboBox()
        self.hash_selector.setObjectName(
            "HashSelector"
        )
        self.hash_selector.addItems(
            self.HASH_OPTIONS.keys()
        )
        self.hash_selector.setCurrentText(
            "SHA-256"
        )

        layout.addWidget(
            self.toolbar_information,
            stretch=1,
        )
        layout.addWidget(
            self.reset_columns_button
        )
        layout.addWidget(
            algorithm_label
        )
        layout.addWidget(
            self.hash_selector
        )

        return toolbar

    def _build_table(self) -> QTableWidget:
        """
        Cria a tabela com colunas responsivas
        e ajustáveis manualmente.
        """

        self.table = QTableWidget()
        self.table.setObjectName(
            "HashTable"
        )

        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                "Arquivo",
                "Extensão",
                "Tamanho",
                "Status",
                "Hash",
            ]
        )

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setAlternatingRowColors(
            False
        )

        self.table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SingleSelection
        )

        self.table.setHorizontalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.table.setVerticalScrollMode(
            QAbstractItemView.ScrollPerPixel
        )

        self.table.setWordWrap(False)
        self.table.setShowGrid(False)

        header = self.table.horizontalHeader()

        # Todas as colunas podem ser ajustadas manualmente.
        header.setSectionResizeMode(
            QHeaderView.Interactive
        )

        # O usuário pode mudar a ordem das colunas.
        header.setSectionsMovable(True)

        # Impede colunas excessivamente pequenas.
        header.setMinimumSectionSize(55)

        # Não força a última coluna a ocupar tudo.
        header.setStretchLastSection(False)

        # Detecta quando o usuário altera uma coluna.
        header.sectionResized.connect(
            self._on_hash_column_resized
        )

        return self.table

    def _connect_signals(self) -> None:
        """
        Conecta os sinais principais da página.
        """

        self.hash_selector.currentTextChanged.connect(
            self.refresh_page
        )

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        """
        Atualiza temporariamente a página
        com apenas um resultado.
        """

        self.results = [result]
        self.refresh_page()

    def update_folder_analysis(
        self,
        results: list[AnalysisResult],
    ) -> None:
        """
        Atualiza a página com uma lista de resultados.
        """

        self.results = list(results)
        self.refresh_page()

    def update_results(
        self,
        results: list[AnalysisResult],
    ) -> None:
        """
        Atualiza a página com todos os resultados
        enviados pelo workspace.
        """

        self.results = list(results)
        self.refresh_page()

    def refresh_page(self) -> None:
        """
        Atualiza os cards, título e tabela.
        """

        hash_groups = (
            self._build_hash_groups()
        )

        self._refresh_summary(
            hash_groups
        )

        self._refresh_table_title()

        self._refresh_table(
            hash_groups
        )

        self._resize_table_columns()

    def resizeEvent(self, event) -> None:
        """
        Executado automaticamente sempre que
        a página muda de tamanho.
        """

        super().resizeEvent(event)

        available_width = (
            event.size().width()
        )

        if available_width < 650:
            columns = 1

        elif available_width < 1000:
            columns = 2

        else:
            columns = 4

        self._reorganize_summary_cards(
            columns
        )

        self._update_toolbar_responsiveness(
            available_width
        )

        self._resize_table_columns()

    def _update_toolbar_responsiveness(
        self,
        available_width: int,
    ) -> None:
        """
        Oculta apenas o texto explicativo quando
        o espaço da página estiver muito reduzido.

        Os controles principais permanecem visíveis.
        """

        self.toolbar_information.setVisible(
            available_width >= 850
        )

    def _reorganize_summary_cards(
        self,
        columns: int,
    ) -> None:
        """
        Reorganiza os cards no grid sem
        destruir os widgets existentes.
        """

        if not hasattr(
            self,
            "summary_cards",
        ):
            return

        if (
            columns
            == self.summary_column_count
        ):
            return

        self.summary_column_count = columns

        for card in self.summary_cards:
            self.summary_layout.removeWidget(
                card
            )

        for index, card in enumerate(
            self.summary_cards
        ):
            row = index // columns
            column = index % columns

            self.summary_layout.addWidget(
                card,
                row,
                column,
            )

        for column in range(4):
            self.summary_layout.setColumnStretch(
                column,
                1 if column < columns else 0,
            )

    def _set_filter(
        self,
        filter_value: HashFilter,
    ) -> None:
        """
        Define o filtro ativo.
        """

        self.current_filter = (
            filter_value
        )

        self.refresh_page()

    def _selected_hash_attribute(
        self,
    ) -> str:
        """
        Retorna o atributo referente
        ao algoritmo selecionado.
        """

        selected_label = (
            self.hash_selector.currentText()
        )

        return self.HASH_OPTIONS.get(
            selected_label,
            "sha256",
        )

    def _hash_value(
        self,
        result: AnalysisResult,
    ) -> str:
        """
        Obtém o valor de hash do resultado.
        """

        hashes = getattr(
            result,
            "hashes",
            None,
        )

        if hashes is None:
            return ""

        attr_name = (
            self._selected_hash_attribute()
        )

        value = getattr(
            hashes,
            attr_name,
            "",
        )

        if value is None:
            return ""

        return str(value).strip().lower()

    def _build_hash_groups(
        self,
    ) -> dict[
        str,
        list[AnalysisResult],
    ]:
        """
        Agrupa resultados pelo hash selecionado.

        Valores vazios não são agrupados.
        """

        groups: dict[
            str,
            list[AnalysisResult],
        ] = defaultdict(list)

        for result in self.results:
            hash_value = self._hash_value(
                result
            )

            if not hash_value:
                continue

            groups[hash_value].append(
                result
            )

        return dict(groups)

    def _refresh_summary(
        self,
        hash_groups: dict[
            str,
            list[AnalysisResult],
        ],
    ) -> None:
        """
        Atualiza os números dos cards.
        """

        total_files = len(
            self.results
        )

        unique_files = sum(
            len(group)
            for group in hash_groups.values()
            if len(group) == 1
        )

        duplicate_files = sum(
            len(group)
            for group in hash_groups.values()
            if len(group) > 1
        )

        duplicate_groups = sum(
            1
            for group in hash_groups.values()
            if len(group) > 1
        )

        self.total_card.set_value(
            total_files
        )

        self.unique_card.set_value(
            unique_files
        )

        self.duplicate_card.set_value(
            duplicate_files
        )

        self.group_card.set_value(
            duplicate_groups
        )

    def _refresh_table_title(self) -> None:
        """
        Atualiza o título da tabela
        conforme o card selecionado.
        """

        titles = {
            self.FILTER_ALL: (
                "Todos os arquivos analisados"
            ),
            self.FILTER_UNIQUE: (
                "Arquivos com hash único"
            ),
            self.FILTER_DUPLICATES: (
                "Arquivos com hash duplicado"
            ),
            self.FILTER_GROUPS: (
                "Grupos de hashes duplicados"
            ),
        }

        self.table_title.setText(
            titles.get(
                self.current_filter,
                "Hashes calculados",
            )
        )

    def _refresh_table(
        self,
        hash_groups: dict[
            str,
            list[AnalysisResult],
        ],
    ) -> None:
        """
        Preenche a tabela conforme o filtro atual.
        """

        visible_results = (
            self._filtered_results(
                hash_groups
            )
        )

        self.table.setRowCount(0)

        has_results = bool(
            visible_results
        )

        self.table.setVisible(
            has_results
        )

        self.empty_label.setVisible(
            not has_results
        )

        if not has_results:
            return

        self.table.setRowCount(
            len(visible_results)
        )

        for row, result in enumerate(
            visible_results
        ):
            hash_value = self._hash_value(
                result
            )

            group_size = len(
                hash_groups.get(
                    hash_value,
                    [],
                )
            )

            self._set_text_item(
                row=row,
                column=0,
                text=result.file_info.name,
            )

            self._set_text_item(
                row=row,
                column=1,
                text=result.file_info.extension,
                alignment=Qt.AlignCenter,
            )

            self._set_text_item(
                row=row,
                column=2,
                text=self._format_size(
                    result.file_info.size_bytes
                ),
                alignment=Qt.AlignCenter,
            )

            self._set_status_widget(
                row=row,
                hash_value=hash_value,
                group_size=group_size,
            )

            self._set_text_item(
                row=row,
                column=4,
                text=(
                    hash_value
                    if hash_value
                    else "Não calculado"
                ),
            )

        self.table.resizeRowsToContents()

    def _filtered_results(
        self,
        hash_groups: dict[
            str,
            list[AnalysisResult],
        ],
    ) -> list[AnalysisResult]:
        """
        Retorna apenas os resultados
        correspondentes ao filtro atual.
        """

        if self.current_filter == (
            self.FILTER_ALL
        ):
            return list(self.results)

        if self.current_filter == (
            self.FILTER_GROUPS
        ):
            representatives: list[
                AnalysisResult
            ] = []

            for group in hash_groups.values():
                if len(group) > 1:
                    representatives.append(
                        group[0]
                    )

            return representatives

        filtered: list[
            AnalysisResult
        ] = []

        for result in self.results:
            hash_value = self._hash_value(
                result
            )

            if not hash_value:
                continue

            group_size = len(
                hash_groups.get(
                    hash_value,
                    [],
                )
            )

            if (
                self.current_filter
                == self.FILTER_UNIQUE
                and group_size == 1
            ):
                filtered.append(result)

            elif (
                self.current_filter
                == self.FILTER_DUPLICATES
                and group_size > 1
            ):
                filtered.append(result)

        return filtered

    def _set_text_item(
        self,
        *,
        row: int,
        column: int,
        text: str,
        alignment: (
            Qt.AlignmentFlag | None
        ) = None,
    ) -> None:
        """
        Insere uma célula textual na tabela.
        """

        item = QTableWidgetItem(
            str(text)
        )

        item.setToolTip(
            str(text)
        )

        if alignment is not None:
            item.setTextAlignment(
                alignment
            )

        self.table.setItem(
            row,
            column,
            item,
        )

    def _set_status_widget(
        self,
        *,
        row: int,
        hash_value: str,
        group_size: int,
    ) -> None:
        """
        Cria o badge de status da linha.
        """

        container = QWidget()
        container.setObjectName(
            "HashStatusContainer"
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            7,
            5,
            7,
            5,
        )
        layout.setAlignment(
            Qt.AlignCenter
        )

        badge = QLabel()
        badge.setObjectName(
            "HashStatusBadge"
        )
        badge.setAlignment(
            Qt.AlignCenter
        )

        if not hash_value:
            badge.setText(
                "Indisponível"
            )
            badge.setProperty(
                "statusType",
                "unavailable",
            )

        elif group_size > 1:
            if self.current_filter == (
                self.FILTER_GROUPS
            ):
                badge.setText(
                    f"Grupo · {group_size} arquivos"
                )
            else:
                badge.setText(
                    f"Duplicado · {group_size}"
                )

            badge.setProperty(
                "statusType",
                "duplicate",
            )

            badge.setToolTip(
                (
                    f"{group_size} arquivos possuem "
                    "o mesmo hash."
                )
            )

        else:
            badge.setText(
                "Único"
            )
            badge.setProperty(
                "statusType",
                "unique",
            )

        layout.addWidget(
            badge
        )

        self.table.setCellWidget(
            row,
            3,
            container,
        )

    def _on_hash_column_resized(
        self,
        logical_index: int,
        old_size: int,
        new_size: int,
    ) -> None:
        """
        Registra que o usuário alterou manualmente
        alguma coluna.

        A partir disso, o programa deixa de substituir
        automaticamente as larguras escolhidas.
        """

        if old_size != new_size:
            self.user_resized_hash_columns = (
                True
            )

    def _resize_table_columns(self) -> None:
        """
        Distribui as colunas proporcionalmente
        enquanto não houver ajuste manual.
        """

        if not hasattr(
            self,
            "table",
        ):
            return

        if self.user_resized_hash_columns:
            return

        available_width = (
            self.table.viewport().width()
        )

        if available_width <= 0:
            return

        # Arquivo: 25%
        # Extensão: 9%
        # Tamanho: 11%
        # Status: 16%
        # Hash: 39%
        proportions = (
            0.25,
            0.09,
            0.11,
            0.16,
            0.39,
        )

        minimum_widths = (
            150,
            75,
            90,
            115,
            220,
        )

        header = (
            self.table.horizontalHeader()
        )

        # Impede que o ajuste automático seja
        # confundido com uma ação do usuário.
        header.blockSignals(True)

        try:
            for column, proportion in enumerate(
                proportions
            ):
                calculated_width = max(
                    minimum_widths[column],
                    int(
                        available_width
                        * proportion
                    ),
                )

                self.table.setColumnWidth(
                    column,
                    calculated_width,
                )

        finally:
            header.blockSignals(False)

    def reset_table_columns(self) -> None:
        """
        Volta ao dimensionamento proporcional automático.
        """

        self.user_resized_hash_columns = (
            False
        )

        self._resize_table_columns()

    @staticmethod
    def _format_size(
        size_bytes: int,
    ) -> str:
        """
        Converte bytes em unidade legível.
        """

        if size_bytes < 1024:
            return f"{size_bytes} B"

        if size_bytes < 1024**2:
            return (
                f"{size_bytes / 1024:.2f} KB"
                .replace(".", ",")
            )

        if size_bytes < 1024**3:
            return (
                f"{size_bytes / 1024**2:.2f} MB"
                .replace(".", ",")
            )

        return (
            f"{size_bytes / 1024**3:.2f} GB"
            .replace(".", ",")
        )
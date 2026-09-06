from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout, QComboBox, QFrame, QHBoxLayout, QLabel, QLineEdit, QProgressBar, QPushButton, QScrollArea,
    QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from app.correlation.v2.pipeline import CanonicalCasePipelineResult
from app.models import AnalysisResult
from app.presentation.correlation_explorer import (
    CaseCorrelationSummary, CorrelationExplorerModel, CrossSourceVerificationGroup,
    CorrelationCategorySummary, ExplorerElement, ExplorerOccurrence, build_case_correlation_summary,
    build_correlation_explorer_model, compact_hash, filter_correlation_elements,
)
from app.presentation.file_type_icons import file_extension_label, file_type_icon_name
from app.ui.line_icons import LineIcon


class _ContentAwareButton(QPushButton):
    """Keyboard-accessible row whose geometry follows its child layout."""

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return hint.expandedTo(self.layout().sizeHint()) if self.layout() is not None else hint

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return hint.expandedTo(self.layout().minimumSize()) if self.layout() is not None else hint


class CorrelationExplorerPage(QWidget):
    """Case-wide, evidence-centric explorer over already calculated facts."""

    artifact_requested = Signal(str)
    source_requested = Signal(str, str)
    MAX_VISIBLE_OCCURRENCES_PER_ARTIFACT = 50

    CATEGORIES = (
        ("all", "Todos os elementos"),
        ("identifiers", "Identificadores"),
        ("identities", "Identidades observadas"),
        ("network", "Rede e ambiente"),
        ("hashes", "Integridade e hashes"),
        ("metadata", "Metadados e origem"),
        ("temporal", "Temporal"),
        ("other", "Outros elementos"),
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("CorrelationExplorerPage")
        self._model = CorrelationExplorerModel(())
        self._case_id: str | None = None
        self._case_fingerprint: tuple[tuple[str, int], ...] = ()
        self._snapshot_fingerprint: int | None = None
        self._canonical_error: str | None = None
        self._selected_id: str | None = None
        self._summary = CaseCorrelationSummary(frozenset(), 0, 0, frozenset(), (), ())
        self._summary_category_scope: frozenset[str] | None = None
        self._setting_summary_filter = False
        self._element_buttons: dict[str, QPushButton] = {}
        self.summary_metric_layout: QBoxLayout | None = None
        self.explorer_controls_layout: QBoxLayout | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 4, 6, 8)
        root.setSpacing(0)
        self.content_stack = QStackedWidget()
        self.summary_view = self._build_summary_view()
        self.explorer_view = QWidget()
        explorer_root = QVBoxLayout(self.explorer_view)
        explorer_root.setContentsMargins(0, 0, 0, 0)
        explorer_root.setSpacing(10)
        back = QPushButton("← Voltar às Correlações")
        back.setObjectName("CorrelationBackButton")
        back.setAccessibleName("Voltar ao resumo de correlações")
        back.clicked.connect(self.show_summary)
        explorer_root.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)

        controls = QHBoxLayout()
        self.explorer_controls_layout = controls
        self.search = QLineEdit()
        self.search.setObjectName("CorrelationExplorerSearch")
        self.search.setPlaceholderText("Buscar CPF, IP, hash, identificador, Produtor...")
        self.search.setClearButtonEnabled(True)
        self.search.setAccessibleName("Buscar valores normalizados nas correlações")
        self.category = QComboBox()
        self.category.setAccessibleName("Filtrar categoria de correlação")
        for key, label in self.CATEGORIES:
            self.category.addItem(label, key)
        self.sorting = QComboBox()
        self.sorting.setAccessibleName("Ordenar elementos de correlação")
        self.sorting.addItem("Ordem técnica", "technical")
        self.sorting.addItem("Nº de artefatos", "artifacts")
        self.sorting.addItem("Nº de ocorrências", "occurrences")
        controls.addWidget(self.search, stretch=1)
        controls.addWidget(self.category)
        controls.addWidget(self.sorting)
        explorer_root.addLayout(controls)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setObjectName("CorrelationExplorerSplitter")
        self.splitter.setChildrenCollapsible(False)
        self.list_scroll, self.list_content, self.list_layout = self._scroll("CorrelationExplorerList")
        self.detail_scroll, self.detail_content, self.detail_layout = self._scroll("CorrelationExplorerDetail")
        self.list_scroll.setMinimumWidth(290)
        self.detail_scroll.setMinimumWidth(380)
        self.splitter.addWidget(self.list_scroll)
        self.splitter.addWidget(self.detail_scroll)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([380, 620])
        explorer_root.addWidget(self.splitter, stretch=1)

        self.verification_view = QWidget()
        self.verification_layout = QVBoxLayout(self.verification_view)
        self.verification_layout.setContentsMargins(0, 0, 0, 0)
        self.verification_layout.setSpacing(8)
        self.content_stack.addWidget(self.summary_view)
        self.content_stack.addWidget(self.explorer_view)
        self.content_stack.addWidget(self.verification_view)
        root.addWidget(self.content_stack)

        self.search.textChanged.connect(self._refresh_list)
        self.category.currentIndexChanged.connect(self._category_changed)
        self.sorting.currentIndexChanged.connect(self._refresh_list)
        self._show_empty_detail()
        self._render_summary()

    def _build_summary_view(self) -> QWidget:
        view = QScrollArea()
        view.setObjectName("CorrelationSummaryScroll")
        view.setWidgetResizable(True)
        view.setFrameShape(QFrame.Shape.NoFrame)
        view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        self.summary_layout = QVBoxLayout(content)
        self.summary_layout.setContentsMargins(2, 0, 8, 8)
        self.summary_layout.setSpacing(12)
        self.summary_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        view.setWidget(content)
        return view

    def _render_summary(self) -> None:
        self._clear(self.summary_layout)
        self.summary_metric_layout = None
        subtitle = QLabel(
            "Visão consolidada das relações técnicas observadas entre os artefatos deste Caso."
        )
        subtitle.setObjectName("PageSubtitle")
        subtitle.setWordWrap(True)
        note = QLabel("Contagens são descritivas e não representam relevância pericial.")
        note.setObjectName("CorrelationDisclaimer")
        self.summary_layout.addWidget(subtitle)
        self.summary_layout.addWidget(note)

        if self._case_id is None:
            self.summary_layout.addWidget(self._note("Nenhum caso selecionado."))
            return
        if not self._summary.analyzed_artifact_count:
            self.summary_layout.addWidget(self._note(
                "A análise do caso ainda não produziu dados de correlação."
            ))
            return
        if self._snapshot_fingerprint is None:
            self.summary_layout.addWidget(self._note(
                f"{self._summary.analyzed_artifact_count} artefato(s) analisado(s)."
            ))
            if self._canonical_error:
                heading = QLabel("LIMITAÇÕES DE ANÁLISE")
                heading.setObjectName("SectionLabel")
                self.summary_layout.addWidget(heading)
                self.summary_layout.addWidget(self._note(self._canonical_error))
            else:
                self.summary_layout.addWidget(self._note(
                    "A análise do caso ainda não produziu dados de correlação."
                ))
            return

        metrics = QFrame()
        metrics.setObjectName("CorrelationSummaryMetrics")
        self.summary_metric_layout = QHBoxLayout(metrics)
        metric_layout = self.summary_metric_layout
        metric_layout.setContentsMargins(0, 10, 0, 10); metric_layout.setSpacing(0)
        correlated = self._metric_button(
            self._summary.correlated_element_count, "elementos correlacionados"
        )
        correlated.clicked.connect(lambda: self.show_explorer())
        metric_layout.addWidget(correlated)
        metric_layout.addWidget(self._metric(
            self._summary.analyzed_artifact_count, "artefatos analisados"
        ))
        metric_layout.addWidget(self._metric(
            self._summary.participating_artifact_count,
            "artefatos com relações interartefato",
        ))
        self._apply_responsive_layout(self.width())
        self.summary_layout.addWidget(metrics)

        coverage = QLabel(
            f"{self._summary.participating_artifact_count} de "
            f"{self._summary.analyzed_artifact_count} artefatos participam de ao menos "
            "uma relação entre artefatos."
        )
        coverage.setObjectName("CorrelationCoverageNote")
        self.summary_layout.addWidget(coverage)

        if not self._summary.correlated_element_count:
            self.summary_layout.addWidget(self._note(
                "Nenhum elemento técnico foi observado em mais de um artefato com os dados atualmente disponíveis."
            ))

        if self._summary.categories:
            heading = QLabel("POR CATEGORIA")
            heading.setObjectName("SectionLabel")
            self.summary_layout.addWidget(heading)
            maximum = max(item.element_count for item in self._summary.categories)
            for category in self._summary.categories:
                self.summary_layout.addWidget(self._category_row(category, maximum))

        if self._summary.verification_groups:
            heading = QLabel("VERIFICAÇÕES ENTRE FONTES")
            heading.setObjectName("SectionLabel")
            self.summary_layout.addWidget(heading)
            for group in self._summary.verification_groups:
                lines = [group.label, f"{len(group.items)} verificação(ões)"]
                lines.extend(f"{count} {state.casefold()}" for state, count in group.state_counts if count)
                button = QPushButton("\n".join(lines))
                button.setObjectName("CorrelationVerificationRow")
                button.clicked.connect(lambda _=False, item=group: self._show_verification_group(item))
                self.summary_layout.addWidget(button)
        else:
            heading = QLabel("VERIFICAÇÕES ENTRE FONTES")
            heading.setObjectName("SectionLabel")
            self.summary_layout.addWidget(heading)
            self.summary_layout.addWidget(self._note(
                "Nenhuma verificação determinística entre fontes está disponível para este caso."
            ))

        if self._model.limitations:
            heading = QLabel("LIMITAÇÕES DE ANÁLISE")
            heading.setObjectName("SectionLabel")
            self.summary_layout.addWidget(heading)
            self.summary_layout.addWidget(self._note(
                f"{len(self._model.limitations)} verificação(ões) não puderam ser concluídas."
            ))
            for limitation in self._model.limitations:
                self.summary_layout.addWidget(self._note(limitation))

        all_button = QPushButton("Ver todos os elementos  →")
        all_button.setObjectName("CorrelationExploreAllButton")
        all_button.clicked.connect(lambda: self.show_explorer())
        self.summary_layout.addWidget(all_button, alignment=Qt.AlignmentFlag.AlignLeft)

    def _show_verification_group(self, group: CrossSourceVerificationGroup) -> None:
        self._clear(self.verification_layout)
        back = QPushButton("← Voltar às Correlações")
        back.setObjectName("CorrelationBackButton")
        back.clicked.connect(self.show_summary)
        self.verification_layout.addWidget(back, alignment=Qt.AlignmentFlag.AlignLeft)
        title = QLabel(group.label.upper())
        title.setObjectName("CorrelationVerificationTitle")
        self.verification_layout.addWidget(title)
        self.verification_layout.addWidget(self._note(f"{len(group.items)} verificação(ões)"))
        scroll, content, layout = self._scroll("CorrelationVerificationDetail")
        for verification in group.items:
            block = QFrame()
            block.setObjectName("CorrelationVerificationBlock")
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(10, 10, 10, 10)
            block_layout.setSpacing(4)
            block_layout.addWidget(QLabel(verification.title))
            rule = QLabel(f"Regra determinística · versão {verification.rule_version}")
            rule.setObjectName("CorrelationProvenance")
            block_layout.addWidget(rule)
            for label, value in verification.details:
                detail = QLabel(f"{label}: {value}")
                detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                block_layout.addWidget(detail)
            state = QLabel(verification.state)
            state.setObjectName("CorrelationVerificationState")
            block_layout.addWidget(state)
            description = QLabel(verification.description)
            description.setObjectName("CorrelationRelationLabel")
            description.setWordWrap(True)
            block_layout.addWidget(description)
            if verification.supporting_occurrences:
                support_title = QLabel("FONTES DE SUPORTE")
                support_title.setObjectName("SectionLabel")
                block_layout.addWidget(support_title)
                for occurrence in verification.supporting_occurrences:
                    support = QLabel(
                        f"{occurrence.artifact_name} · {occurrence.provenance_label}"
                    )
                    support.setWordWrap(True)
                    support.setObjectName("CorrelationProvenance")
                    block_layout.addWidget(support)
            layout.addWidget(block)
        self.verification_layout.addWidget(scroll)
        self.content_stack.setCurrentWidget(self.verification_view)

    @staticmethod
    def _metric(value: int, label: str) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(14, 0, 14, 0)
        number = QLabel(str(value))
        number.setObjectName("CorrelationMetricValue")
        caption = QLabel(label)
        caption.setObjectName("CorrelationMetricLabel")
        caption.setWordWrap(True)
        layout.addWidget(number)
        layout.addWidget(caption)
        return widget

    @staticmethod
    def _metric_button(value: int, label: str) -> QPushButton:
        button = QPushButton(f"{value}\n{label}")
        button.setObjectName("CorrelationMetricButton")
        return button

    def _category_row(self, category: CorrelationCategorySummary, maximum: int) -> QPushButton:
        button = _ContentAwareButton()
        button.setObjectName("CorrelationSummaryRow")
        button.setAccessibleName(
            f"Abrir {category.label}: {category.element_count} elementos correlacionados"
        )
        layout = QHBoxLayout(button)
        layout.setContentsMargins(10, 7, 10, 7); layout.setSpacing(10)
        label = QLabel(category.label); label.setObjectName("CorrelationCategoryLabel")
        bar = QProgressBar(); bar.setObjectName("CorrelationCategoryBar")
        bar.setRange(0, max(1, maximum)); bar.setValue(category.element_count)
        bar.setTextVisible(False); bar.setAccessibleName(
            f"{category.element_count} elementos em {category.label}"
        )
        count = QLabel(str(category.element_count)); count.setObjectName("CorrelationCategoryCount")
        layout.addWidget(label, 2); layout.addWidget(bar, 3); layout.addWidget(count)
        layout.addWidget(LineIcon("chevron-right", button, 15))
        button.clicked.connect(lambda _=False, key=category.key: self.show_explorer(key))
        return button

    @staticmethod
    def _scroll(name: str) -> tuple[QScrollArea, QWidget, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName(name)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll, content, layout

    def update_case(
        self, case_id: str | None, results: list[AnalysisResult],
        snapshot: CanonicalCasePipelineResult | None,
        canonical_error: str | None = None,
    ) -> None:
        fingerprint = tuple(sorted(
            (str(Path(result.file_info.path).resolve()), id(result)) for result in results
        ))
        snapshot_fingerprint = id(snapshot) if snapshot is not None else None
        if (
            case_id == self._case_id
            and fingerprint == self._case_fingerprint
            and snapshot_fingerprint == self._snapshot_fingerprint
            and canonical_error == self._canonical_error
        ):
            return
        if snapshot is not None and snapshot.case_result.case_id != case_id:
            return
        case_changed = case_id != self._case_id
        self._case_id = case_id; self._case_fingerprint = fingerprint
        self._snapshot_fingerprint = snapshot_fingerprint
        self._canonical_error = canonical_error
        self._model = build_correlation_explorer_model(snapshot) if snapshot is not None else CorrelationExplorerModel(())
        self._summary = build_case_correlation_summary(self._model, results)
        if case_changed:
            self.search.clear(); self.category.setCurrentIndex(0); self.sorting.setCurrentIndex(0)
            self._summary_category_scope = None; self._selected_id = None
            self.show_summary()
        if self._selected_id not in {item.stable_id for item in self._model.elements}:
            self._selected_id = None
        self._refresh_list()
        self._render_summary()

    def show_summary(self) -> None:
        self.content_stack.setCurrentWidget(self.summary_view)

    def show_explorer(self, category: str | None = None) -> None:
        self._setting_summary_filter = True
        try:
            if category == "identities":
                self.category.setCurrentIndex(0)
                self._summary_category_scope = frozenset({"identifiers", "identities"})
            elif category is None:
                self.category.setCurrentIndex(0)
                self._summary_category_scope = None
            else:
                index = self.category.findData(category)
                self.category.setCurrentIndex(max(0, index))
                self._summary_category_scope = frozenset({category})
        finally:
            self._setting_summary_filter = False
        self._refresh_list()
        self.content_stack.setCurrentWidget(self.explorer_view)

    def _category_changed(self) -> None:
        if not self._setting_summary_filter:
            self._summary_category_scope = None
        self._refresh_list()

    def _refresh_list(self) -> None:
        self._clear(self.list_layout)
        self._element_buttons.clear()
        visible = filter_correlation_elements(
            self._model.elements, self.search.text(),
            str(self.category.currentData() or "all"),
            str(self.sorting.currentData() or "technical"),
        )
        visible = tuple(
            item for item in visible
            if item.stable_id in self._summary.correlated_element_ids
            and (
                self._summary_category_scope is None
                or item.category in self._summary_category_scope
            )
        )
        if self.sorting.currentData() == "artifacts":
            self.list_layout.addWidget(self._note("Ordenado por número de artefatos; a ordem não expressa relevância."))
        elif self.sorting.currentData() == "occurrences":
            self.list_layout.addWidget(self._note("Ordenado por ocorrências; frequência não altera o estado epistêmico."))
        if not visible:
            self.list_layout.addWidget(self._note("Nenhum elemento técnico corresponde aos filtros."))
            self._show_empty_detail()
            return
        for element in visible:
            button = _ContentAwareButton()
            button.setObjectName("CorrelationElementRow")
            button.setCheckable(True)
            button.setChecked(element.stable_id == self._selected_id)
            button.setAccessibleName(
                f"{element.type_label}: {element.display_value}; "
                f"{element.artifact_count} artefatos, {element.occurrence_count} ocorrências"
            )
            row = QVBoxLayout(button)
            row.setContentsMargins(12, 10, 10, 10)
            row.setSpacing(4)
            category = QLabel(element.type_label.upper())
            category.setObjectName("CorrelationElementCategory")
            shown_value = (
                compact_hash(element.display_value)
                if element.category == "hashes" else element.display_value
            )
            heading = QLabel(shown_value)
            heading.setObjectName("CorrelationElementTitle")
            heading.setWordWrap(True)
            footer = QHBoxLayout()
            counts = QLabel(self._counts(element.artifact_count, element.occurrence_count))
            counts.setObjectName("CorrelationElementCounts")
            chevron = LineIcon("chevron-right", button, 15)
            footer.addWidget(counts, stretch=1)
            footer.addWidget(chevron)
            row.addWidget(category)
            row.addWidget(heading)
            row.addLayout(footer)
            button.clicked.connect(lambda _=False, item=element: self._select(item))
            self._element_buttons[element.stable_id] = button
            self.list_layout.addWidget(button)
        selected = next((item for item in visible if item.stable_id == self._selected_id), None)
        if selected is not None:
            self._render_detail(selected)

    def _select(self, element: ExplorerElement) -> None:
        self._selected_id = element.stable_id
        for stable_id, button in self._element_buttons.items():
            button.setChecked(stable_id == element.stable_id)
        self._render_detail(element)

    def _render_detail(self, element: ExplorerElement) -> None:
        self._clear(self.detail_layout)
        kind = QLabel(element.type_label.upper())
        kind.setObjectName("SidebarSectionTitle")
        value = QLabel(element.display_value)
        value.setObjectName("CorrelationDetailValue")
        value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        value.setWordWrap(True)
        counts = QLabel(self._counts(element.artifact_count, element.occurrence_count))
        counts.setObjectName("CorrelationElementCounts")
        relation = QLabel(element.relation_label)
        relation.setObjectName("CorrelationRelationLabel")
        relation.setWordWrap(True)
        self.detail_layout.addWidget(kind)
        self.detail_layout.addWidget(value)
        self.detail_layout.addWidget(counts)
        self.detail_layout.addWidget(relation)
        raw_values = tuple(dict.fromkeys(item.raw_value for item in element.occurrences))
        if raw_values and raw_values[0] != element.display_value:
            raw = QLabel(f"Valor original: {raw_values[0]}")
            raw.setObjectName("CorrelationRawValue")
            raw.setWordWrap(True)
            raw.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            self.detail_layout.addWidget(raw)
        if element.deterministic_state:
            state = QLabel(f"Resultado determinístico: {element.deterministic_state}")
            state.setObjectName("CorrelationDeterministicState")
            self.detail_layout.addWidget(state)

        by_artifact: dict[str, list[ExplorerOccurrence]] = defaultdict(list)
        for occurrence in element.occurrences:
            by_artifact[occurrence.artifact_id].append(occurrence)
        for occurrences in by_artifact.values():
            self.detail_layout.addWidget(self._artifact_block(occurrences))

    def _artifact_block(self, occurrences: list[ExplorerOccurrence]) -> QWidget:
        first = occurrences[0]
        block = QFrame()
        block.setObjectName("CorrelationArtifactBlock")
        layout = QVBoxLayout(block)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)
        artifact_row = QHBoxLayout()
        icon = LineIcon(file_type_icon_name(first.artifact_name), block, 20)
        extension = file_extension_label(first.artifact_name)
        artifact = QPushButton(first.artifact_name)
        artifact.setObjectName("CorrelationArtifactLink")
        artifact.setToolTip(first.artifact_path or first.artifact_name)
        artifact.setAccessibleName(f"Selecionar artefato {first.artifact_name}")
        if first.artifact_path:
            artifact.clicked.connect(lambda _=False, path=first.artifact_path: self.artifact_requested.emit(path))
        extension_label = QLabel(extension)
        extension_label.setObjectName("CorrelationFileExtension")
        count = QLabel(self._occurrence_count(len(occurrences)))
        count.setObjectName("CorrelationElementCounts")
        artifact_row.addWidget(icon)
        artifact_row.addWidget(artifact, stretch=1)
        artifact_row.addWidget(extension_label)
        artifact_row.addWidget(count)
        layout.addLayout(artifact_row)
        visible_occurrences = occurrences[:self.MAX_VISIBLE_OCCURRENCES_PER_ARTIFACT]
        for occurrence in visible_occurrences:
            provenance = QLabel(f"Fonte: {occurrence.provenance_label}")
            provenance.setObjectName("CorrelationProvenance")
            provenance.setWordWrap(True)
            provenance.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            layout.addWidget(provenance)
        hidden_count = len(occurrences) - len(visible_occurrences)
        if hidden_count:
            layout.addWidget(self._note(
                f"{hidden_count} ocorrência(s) adicional(is) preservada(s) no modelo canônico; "
                "a visualização foi limitada para manter a interface responsiva."
            ))
        if first.artifact_path:
            source = QPushButton("Abrir vestígio técnico")
            source.setObjectName("InlineActionButton")
            source.setAccessibleName(
                f"Abrir vestígio técnico de {first.artifact_name}; foco exato pode não estar disponível"
            )
            source.clicked.connect(
                lambda _=False, path=first.artifact_path, occurrence=first.occurrence_id:
                self.source_requested.emit(path, occurrence)
            )
            layout.addWidget(source, alignment=Qt.AlignmentFlag.AlignLeft)
        return block

    def _show_empty_detail(self) -> None:
        self._clear(self.detail_layout)
        self.detail_layout.addWidget(self._note(
            "Selecione um elemento para explorar os artefatos e as ocorrências associadas."
        ))

    def resizeEvent(self, event) -> None:
        self._apply_responsive_layout(event.size().width())
        super().resizeEvent(event)

    def _apply_responsive_layout(self, width: int) -> None:
        narrow = width < 760
        self.splitter.setOrientation(
            Qt.Orientation.Vertical if narrow else Qt.Orientation.Horizontal
        )
        if self.summary_metric_layout is not None:
            self.summary_metric_layout.setDirection(
                QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
            )
        if self.explorer_controls_layout is not None:
            self.explorer_controls_layout.setDirection(
                QBoxLayout.Direction.TopToBottom if narrow else QBoxLayout.Direction.LeftToRight
            )

    @staticmethod
    def _counts(artifacts: int, occurrences: int) -> str:
        artifact_label = "artefato" if artifacts == 1 else "artefatos"
        occurrence_label = "ocorrência" if occurrences == 1 else "ocorrências"
        return f"{artifacts} {artifact_label} · {occurrences} {occurrence_label}"

    @staticmethod
    def _occurrence_count(count: int) -> str:
        return f"{count} {'ocorrência' if count == 1 else 'ocorrências'}"

    @staticmethod
    def _note(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("EmptyStateText")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _clear(layout: QVBoxLayout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

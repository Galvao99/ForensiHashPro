from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QButtonGroup, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout, QWidget,
)

from app.models import AnalysisResult
from app.models.comparison_view import ComparisonView, DiffField
from app.services.analysis_service import AnalysisService
from app.services.comparison_service import ComparisonService, artifact_id
from app.widgets.flow_layout import FlowLayout


def _size(value: int) -> str:
    amount = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if amount < 1024 or unit == "GB":
            return f"{amount:.0f} {unit}" if unit == "B" else f"{amount:.1f} {unit}"
        amount /= 1024
    return f"{value} B"


class ArtifactNode(QPushButton):
    def __init__(self, result: AnalysisResult) -> None:
        super().__init__()
        self.result = result
        self.identity = artifact_id(result)
        kind = result.magic_numbers.detected_format or result.file_info.extension.lstrip(".").upper() or "FILE"
        status = "CONCLUÍDO" if result.completed_at else "ANALISADO"
        self._kind = kind
        self._details = f"{result.file_info.name}\n{_size(result.file_info.size_bytes)} · {status}"
        self.setText(f"{kind}\n{self._details}")
        self.setCheckable(True)
        self.setObjectName("ArtifactNode")
        self.setProperty("slot", "")
        self.setToolTip(result.file_info.name)
        self.setAccessibleName(f"Artefato {result.file_info.name}")
        self.setMinimumSize(210, 106)
        self.setMaximumWidth(290)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def set_slot(self, slot: str | None) -> None:
        self.setChecked(slot is not None)
        self.setProperty("slot", slot or "")
        self.setText(f"{self._kind}{f'  ·  {slot}' if slot else ''}\n{self._details}")
        self.style().unpolish(self)
        self.style().polish(self)


class ElidedLabel(QLabel):
    def __init__(self, text: str = "") -> None:
        super().__init__()
        self._full_text = text
        self.setToolTip(text)

    def setText(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self._update_elision()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_elision()

    def _update_elision(self) -> None:
        width = max(20, self.contentsRect().width())
        QLabel.setText(self, QFontMetrics(self.font()).elidedText(self._full_text, Qt.TextElideMode.ElideMiddle, width))


class ComparisonPairHeader(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("ComparisonPairHeader")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.left = self._artifact_panel("A")
        self.connector = QLabel("↔\nPAR")
        self.connector.setObjectName("ComparisonConnector")
        self.connector.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right = self._artifact_panel("B")
        layout.addWidget(self.left, 1)
        layout.addWidget(self.connector)
        layout.addWidget(self.right, 1)

    def _artifact_panel(self, slot: str) -> QFrame:
        panel = QFrame()
        panel.setObjectName("ComparisonArtifactPanel")
        box = QVBoxLayout(panel)
        box.setContentsMargins(14, 10, 14, 10)
        box.setSpacing(3)
        slot_label = QLabel(f"ARTEFATO {slot}")
        slot_label.setObjectName("ComparisonArtifactSlot")
        name = ElidedLabel()
        name.setObjectName("ComparisonArtifactName")
        details = QLabel()
        details.setObjectName("ComparisonArtifactDetails")
        digest = ElidedLabel()
        digest.setObjectName("ComparisonArtifactHash")
        box.addWidget(slot_label); box.addWidget(name); box.addWidget(details); box.addWidget(digest)
        panel.name_label = name
        panel.details_label = details
        panel.hash_label = digest
        panel.setMinimumWidth(250)
        return panel

    def update_pair(self, left: AnalysisResult, right: AnalysisResult) -> None:
        self._update_panel(self.left, left)
        self._update_panel(self.right, right)

    @staticmethod
    def _update_panel(panel: QFrame, result: AnalysisResult) -> None:
        kind = result.magic_numbers.detected_format or result.file_info.extension.lstrip(".").upper()
        panel.name_label.setText(result.file_info.name)
        panel.details_label.setText(f"{kind} · {_size(result.file_info.size_bytes)}")
        panel.hash_label.setText(f"SHA-256  {result.hashes.sha256}")


class TechnicalMatchesSummary(QFrame):
    INITIAL_LIMIT = 4

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TechnicalMatches")
        self._matches: tuple[tuple[str, str, str], ...] = ()
        self._expanded = False
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        header = QHBoxLayout()
        title = QLabel("CORRESPONDÊNCIAS TÉCNICAS")
        title.setObjectName("TechnicalMatchesTitle")
        self.count = QLabel("0")
        self.count.setObjectName("TechnicalMatchesCount")
        header.addWidget(title); header.addStretch(); header.addWidget(self.count)
        self.rows = QWidget()
        self.rows_layout = QVBoxLayout(self.rows)
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(0)
        self.toggle = QPushButton()
        self.toggle.setObjectName("TechnicalMatchesToggle")
        self.toggle.clicked.connect(self.toggle_expanded)
        root.addLayout(header); root.addWidget(self.rows); root.addWidget(self.toggle)

    @property
    def expanded(self) -> bool:
        return self._expanded

    def set_matches(self, matches: tuple[tuple[str, str, str], ...]) -> None:
        self._matches = matches
        self._expanded = False
        self._refresh()

    def toggle_expanded(self) -> None:
        self._expanded = not self._expanded
        self._refresh()

    def _refresh(self) -> None:
        while self.rows_layout.count():
            item = self.rows_layout.takeAt(0)
            if item and item.widget(): item.widget().deleteLater()
        shown = self._matches if self._expanded else self._matches[:self.INITIAL_LIMIT]
        for group, key, value in shown:
            row = QFrame(); row.setObjectName("TechnicalMatchRow")
            layout = QHBoxLayout(row); layout.setContentsMargins(10, 5, 10, 5)
            label_text = (
                "SHA-256 dos artefatos correspondente"
                if group == "Hashes" and key == "SHA256"
                else key
            )
            label = QLabel(label_text)
            label.setObjectName("TechnicalMatchKey")
            content = ElidedLabel(value); content.setObjectName("TechnicalMatchValue")
            layout.addWidget(label, 2); layout.addWidget(content, 5)
            self.rows_layout.addWidget(row)
        total = len(self._matches)
        self.count.setText(str(total))
        self.toggle.setVisible(total > self.INITIAL_LIMIT)
        self.toggle.setText("Recolher correspondências" if self._expanded else f"Ver todas as {total} correspondências")


class ComparisonWorkspace(QWidget):
    """Workspace explícito A ↔ B; não produz correlações investigativas."""

    focus_mode_requested = Signal(bool)

    def __init__(self, analysis_service: AnalysisService, comparison_service: ComparisonService | None = None) -> None:
        super().__init__()
        self.analysis_service = analysis_service  # compatibilidade de construção/injeção
        self.comparison_service = comparison_service or ComparisonService()
        self.results: list[AnalysisResult] = []
        self.selected_ids: list[str] = []
        self.nodes: dict[str, ArtifactNode] = {}
        self.comparison_result: ComparisonView | None = None
        self.left_result: AnalysisResult | None = None
        self.right_result: AnalysisResult | None = None
        self.current_filter = "all"
        self.focus_mode = False
        self.stack = QStackedWidget()
        self.workspace_page = self._build_workspace()
        self.result_page = self._build_result()
        self.stack.addWidget(self.workspace_page)
        self.stack.addWidget(self.result_page)
        self.installEventFilter(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)

    def _build_workspace(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        intro = QLabel("Selecione dois artefatos para comparar")
        intro.setObjectName("ComparisonTitle")
        subtitle = QLabel("A conexão indica apenas o par escolhido; não representa correlação.")
        subtitle.setObjectName("SectionSubtitle")
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por filename")
        self.search.textChanged.connect(self._filter_nodes)
        self.empty_message = QLabel("Nenhum artefato analisado no workspace.")
        self.empty_message.setWordWrap(True)
        self.canvas_widget = QWidget()
        self.canvas = FlowLayout(self.canvas_widget, horizontal_spacing=12, vertical_spacing=12)
        scroll = QScrollArea()
        scroll.setObjectName("ComparisonCanvas")
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.canvas_widget)
        self.pair_status = QLabel("Selecione o artefato A.")
        self.pair_status.setObjectName("ComparisonPairStatus")
        self.comparability = QLabel()
        self.comparability.setWordWrap(True)
        self.execute_button = QPushButton("EXECUTAR COMPARAÇÃO")
        self.execute_button.setObjectName("ComparisonExecuteButton")
        self.execute_button.setEnabled(False)
        self.execute_button.clicked.connect(self.execute_comparison)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(intro)
        layout.addWidget(subtitle)
        layout.addWidget(self.search)
        layout.addWidget(self.empty_message)
        layout.addWidget(self.summary_label)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.pair_status)
        layout.addWidget(self.comparability)
        layout.addWidget(self.execute_button)
        return page

    def _build_result(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        actions = QHBoxLayout()
        back = QPushButton("← Voltar aos artefatos")
        back.setObjectName("ComparisonBackButton")
        back.clicked.connect(self.back_to_artifacts)
        self.focus_button = QPushButton("Expandir comparação")
        self.focus_button.setObjectName("ComparisonFocusButton")
        self.focus_button.clicked.connect(self.toggle_focus_mode)
        actions.addWidget(back); actions.addStretch(); actions.addWidget(self.focus_button)
        eyebrow = QLabel("COMPARANDO AGORA")
        eyebrow.setObjectName("ResultEyebrow")
        self.pair_header = ComparisonPairHeader()
        self.matches_summary = TechnicalMatchesSummary()
        diff_heading = QHBoxLayout()
        diff_title = QLabel("COMPARAÇÃO DETALHADA")
        diff_title.setObjectName("ComparisonDiffTitle")
        diff_note = QLabel("A e B são os artefatos selecionados; não representam antes/depois.")
        diff_note.setObjectName("SectionSubtitle")
        diff_heading.addWidget(diff_title); diff_heading.addStretch(); diff_heading.addWidget(diff_note)
        filters = QHBoxLayout()
        self.filter_group = QButtonGroup(self)
        for key, text in (("all", "Tudo"), ("changed", "Alterações"), ("match", "Correspondências")):
            button = QPushButton(text)
            button.setCheckable(True)
            button.setObjectName("ComparisonFilterButton")
            button.setProperty("filter", key)
            self.filter_group.addButton(button)
            filters.addWidget(button)
            if key == "all": button.setChecked(True)
        self.filter_group.buttonClicked.connect(self._apply_filter)
        filters.addStretch()
        self.diff_content = QWidget()
        self.diff_layout = QVBoxLayout(self.diff_content)
        self.diff_scroll = QScrollArea()
        self.diff_scroll.setObjectName("ComparisonDiffScroll")
        self.diff_scroll.setWidgetResizable(True)
        self.diff_scroll.setWidget(self.diff_content)
        layout.addLayout(actions)
        layout.addWidget(eyebrow)
        layout.addWidget(self.pair_header)
        layout.addWidget(self.matches_summary)
        layout.addLayout(diff_heading)
        layout.addLayout(filters)
        layout.addWidget(self.diff_scroll, 1)
        return page

    def update_results(self, results: list[AnalysisResult]) -> None:
        self.results = list(results)
        while self.canvas.count():
            item = self.canvas.takeAt(0)
            if item and item.widget(): item.widget().deleteLater()
        self.nodes.clear()
        for result in self.results:
            identity = artifact_id(result)
            node = ArtifactNode(result)
            node.clicked.connect(partial(self._select, identity))
            self.nodes[identity] = node
            self.canvas.addWidget(node)
        self.selected_ids = [identity for identity in self.selected_ids if identity in self.nodes][:2]
        self.empty_message.setText("Adicione outro artefato para realizar uma comparação." if len(results) == 1 else "Nenhum artefato analisado no workspace.")
        self.empty_message.setVisible(len(results) < 2)
        self.search.setVisible(len(results) >= 8)
        self._refresh_selection()

    def _select(self, identity: str) -> None:
        if identity in self.selected_ids:
            self.selected_ids.remove(identity)
        elif len(self.selected_ids) >= 2:
            self.nodes[identity].setChecked(False)
            QMessageBox.information(self, "Par de comparação", "Já existem dois artefatos selecionados. Remova A ou B primeiro.")
            return
        else:
            self.selected_ids.append(identity)
        self._refresh_selection()

    def _refresh_selection(self) -> None:
        for identity, node in self.nodes.items():
            slot = "A" if self.selected_ids[:1] == [identity] else "B" if len(self.selected_ids) > 1 and self.selected_ids[1] == identity else None
            node.set_slot(slot)
        count = len(self.selected_ids)
        self.execute_button.setEnabled(count == 2)
        self.pair_status.setText("Selecione o artefato A." if count == 0 else "A selecionado. Selecione o artefato B." if count == 1 else "A ───── COMPARAR ───── B")
        self.comparability.setText("")
        if count == 2:
            left, right = self._pair()
            items = self.comparison_service.comparable_dimensions(left, right)
            self.comparability.setText("Comparável em:  " + "  ".join(("✓ " if ok else "○ ") + name for name, ok in items))

    def execute_comparison(self) -> None:
        if len(self.selected_ids) != 2:
            return
        left, right = self._pair()
        self.comparison_result = self.comparison_service.compare(left, right)
        self.pair_header.update_pair(left, right)
        self.current_filter = "all"
        self.matches_summary.set_matches(self.comparison_result.matches)
        self._render(self.comparison_result, self.current_filter)
        self.stack.setCurrentWidget(self.result_page)

    def _render(self, view: ComparisonView, filter_key: str) -> None:
        while self.diff_layout.count():
            item = self.diff_layout.takeAt(0)
            if item and item.widget(): item.widget().deleteLater()
        for group in view.groups:
            fields = [field for field in group.fields if filter_key == "all" or filter_key == "match" and field.state == "match" or filter_key == "changed" and field.state != "match"]
            if not fields: continue
            section = QFrame()
            section.setObjectName("ComparisonDiffSection")
            box = QVBoxLayout(section)
            title = QLabel(group.title.upper())
            title.setObjectName("SummarySectionTitle")
            box.addWidget(title)
            for field in fields:
                box.addWidget(self._diff_field(field))
            self.diff_layout.addWidget(section)
        self.diff_layout.addStretch()

    @staticmethod
    def _diff_field(field: DiffField) -> QWidget:
        frame = QFrame()
        frame.setObjectName("DiffField")
        frame.setProperty("state", field.state)
        layout = QVBoxLayout(frame)
        status = {"match": "CORRESPONDENTE", "changed": "ALTERADO", "left_only": "SOMENTE A", "right_only": "SOMENTE B"}[field.state]
        layout.addWidget(QLabel(f"{field.key}  ·  {status}"))
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName("ComparisonDiffSplitter")
        splitter.setChildrenCollapsible(False)
        left = QLabel(f"A\n- {field.left if field.left is not None else 'Não disponível'}")
        right = QLabel(f"B\n+ {field.right if field.right is not None else 'Não disponível'}")
        left.setWordWrap(True); right.setWordWrap(True)
        left.setMinimumWidth(180); right.setMinimumWidth(180)
        left.setObjectName("DiffValueA"); right.setObjectName("DiffValueB")
        splitter.addWidget(left); splitter.addWidget(right)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter)
        return frame

    def _apply_filter(self, button: QPushButton) -> None:
        if self.comparison_result:
            self.current_filter = button.property("filter")
            self._render(self.comparison_result, self.current_filter)

    def toggle_focus_mode(self) -> None:
        self.set_focus_mode(not self.focus_mode)

    def back_to_artifacts(self) -> None:
        if self.focus_mode:
            self.set_focus_mode(False)
        self.stack.setCurrentWidget(self.workspace_page)

    def set_focus_mode(self, enabled: bool) -> None:
        self.focus_mode = enabled
        self.focus_button.setText("Sair do modo expandido" if enabled else "Expandir comparação")
        self.focus_mode_requested.emit(enabled)

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Escape and self.focus_mode:
            self.set_focus_mode(False)
            return True
        return super().eventFilter(watched, event)

    def _filter_nodes(self, text: str) -> None:
        query = text.strip().casefold()
        for node in self.nodes.values():
            node.setVisible(query in node.result.file_info.name.casefold())

    def _pair(self) -> tuple[AnalysisResult, AnalysisResult]:
        lookup = {artifact_id(result): result for result in self.results}
        return lookup[self.selected_ids[0]], lookup[self.selected_ids[1]]

    def clear_comparison(self) -> None:
        self.selected_ids.clear()
        self.comparison_result = None
        self.stack.setCurrentWidget(self.workspace_page)
        self._refresh_selection()

    # Compatibilidade com integrações legadas. O fluxo novo não expõe estes
    # seletores e nunca os chama automaticamente.
    def select_left_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo A")
        if not filename:
            return
        self.left_result = self.analysis_service.analyze(Path(filename))
        if hasattr(self, "left_label"):
            self.left_label.setText(f"Arquivo A: {self.left_result.file_info.name}")
        if hasattr(self, "try_compare"):
            self.try_compare()

    def update_dashboard(self, result: object) -> None:
        sections = list(getattr(result, "sections", ()))
        compatible = sum(getattr(item, "status", "") == "success" for item in sections)
        divergent = sum(getattr(item, "status", "") in {"warning", "critical"} for item in sections)
        not_applicable = sum(getattr(item, "status", "") == "info" for item in sections)
        self.summary_label.setText(
            f"{compatible} item(ns) compatível(is), {divergent} divergente(s) e "
            f"{not_applicable} não aplicável(is)."
        )

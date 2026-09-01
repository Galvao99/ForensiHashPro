from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QHeaderView, QLabel, QMessageBox, QPushButton, QScrollArea,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from app.observability import HealthCheckService, ObservabilityService, export_diagnostic
from app.observability.models import ObservabilitySnapshot, OperationalStatus
from app.presentation.diagnostics_formatting import format_bytes, format_count, format_duration
from app.widgets.diagnostics import (
    DiagnosticsMetricCard, EngineTimeChart, FileStatusDistribution,
    OperationalStatusBadge, STATUS_PRESENTATION,
)

STATUS_PRIORITY = {OperationalStatus.ERROR: 0, OperationalStatus.DEGRADED: 1,
                   OperationalStatus.UNAVAILABLE: 2, OperationalStatus.OK: 3}


class NumericItem(QTableWidgetItem):
    def __init__(self, display: str, value: float) -> None:
        super().__init__(display); self.value = value

    def __lt__(self, other: QTableWidgetItem) -> bool:
        return self.value < getattr(other, "value", 0)


class DiagnosticsPage(QWidget):
    """Dashboard operacional local; apresenta snapshots sem executar análise."""

    def __init__(self, observability: ObservabilityService, health_checks: HealthCheckService) -> None:
        super().__init__(); self.observability = observability; self.health_checks = health_checks
        self._snapshot: ObservabilitySnapshot | None = None; self._engine_rows = {}
        self._engine_initial_sort = True
        self.setObjectName("DiagnosticsPage"); self._build_ui(); self._connect()
        self.timer = QTimer(self); self.timer.timeout.connect(self.refresh); self.timer.start(1500); self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        actions = QHBoxLayout(); self.status_filter = QComboBox(); self.status_filter.addItems(("Todos os estados", "ERROR", "DEGRADED", "UNAVAILABLE", "OK"))
        self.engine_filter = QComboBox(); self.engine_filter.addItem("Todos os componentes", "")
        self.refresh_button = QPushButton("Atualizar"); self.run_button = QPushButton("Executar diagnóstico")
        self.copy_summary_button = QPushButton("Copiar resumo"); self.export_button = QPushButton("Exportar JSON")
        for widget in (self.status_filter, self.engine_filter, self.refresh_button, self.run_button, self.copy_summary_button, self.export_button): actions.addWidget(widget)
        actions.addStretch(); root.addLayout(actions)
        self.scroll = QScrollArea(); self.scroll.setWidgetResizable(True); self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget(); self.body_layout = QVBoxLayout(body); self.body_layout.setContentsMargins(0, 0, 6, 0); self.body_layout.setSpacing(12)
        self._build_cards(); self._build_case(); self._build_engines(); self._build_jobs(); self._build_errors(); self._build_environment()
        self.body_layout.addStretch(); self.scroll.setWidget(body); root.addWidget(self.scroll)

    def _build_cards(self) -> None:
        grid = QGridLayout(); self.cards = {}
        for index, (key, title) in enumerate((('health', 'Status geral'), ('engines', 'Engines / componentes'), ('performance', 'Performance'), ('errors', 'Erros recentes'), ('jobs', 'Jobs ativos'))):
            card = DiagnosticsMetricCard(title); grid.addWidget(card, index // 3, index % 3); self.cards[key] = card
        self.health_badge = OperationalStatusBadge(); self.cards["health"].layout().insertWidget(1, self.health_badge); self.cards["health"].value.setVisible(False)
        self.card_labels = {key: card.value for key, card in self.cards.items()}; self.body_layout.addLayout(grid)

    def _build_case(self) -> None:
        self.case = QGroupBox("Performance do Caso atual"); box = QVBoxLayout(self.case); grid = QGridLayout(); self.case_labels = {}
        for index, (key, title) in enumerate((("case_ref", "Caso/ref"), ("files", "Arquivos"), ("size", "Tamanho total"), ("ingestion", "Ingestão"), ("first", "Primeiro resultado"), ("total", "Análise total"), ("cache", "Cache"))):
            frame = QFrame(); frame.setObjectName("DiagnosticsFact"); layout = QVBoxLayout(frame); layout.setContentsMargins(10, 7, 10, 7)
            caption = QLabel(title); caption.setObjectName("DiagnosticsFactTitle"); value = QLabel("—"); value.setObjectName("DiagnosticsFactValue")
            layout.addWidget(caption); layout.addWidget(value); grid.addWidget(frame, index // 4, index % 4); self.case_labels[key] = value
        box.addLayout(grid); self.file_distribution = FileStatusDistribution(); box.addWidget(self.file_distribution); self.body_layout.addWidget(self.case)

    def _build_engines(self) -> None:
        section = QGroupBox("Engines e dependências"); layout = QVBoxLayout(section)
        self.components = self._table(("Componente", "Status", "Versão", "Último check/execution", "Tempo médio", "Última duração", "Execuções", "Falhas", "Tempo total"), 220)
        self.components.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.components.setSortingEnabled(True); layout.addWidget(self.components)
        self.engine_details = QLabel("Selecione um componente para ver detalhes operacionais."); self.engine_details.setObjectName("DiagnosticsDetails"); self.engine_details.setWordWrap(True); layout.addWidget(self.engine_details)
        title = QLabel("Distribuição do tempo instrumentado por engine"); title.setObjectName("CardTitle"); layout.addWidget(title)
        self.engine_chart = EngineTimeChart(); layout.addWidget(self.engine_chart); self.body_layout.addWidget(section)

    def _build_jobs(self) -> None:
        section = QGroupBox("Jobs ativos"); layout = QVBoxLayout(section); self.jobs_empty = self._empty("Nenhum job ativo.")
        self.jobs = self._table(("Arquivo/ref", "Engine/operação", "Estado", "Início", "Duração", "Progresso"), 110)
        layout.addWidget(self.jobs_empty); layout.addWidget(self.jobs); self.body_layout.addWidget(section)

    def _build_errors(self) -> None:
        section = QGroupBox("Erros operacionais recentes"); layout = QVBoxLayout(section); filters = QHBoxLayout()
        self.error_component_filter = QComboBox(); self.error_code_filter = QComboBox(); self.error_class_filter = QComboBox()
        for combo, label in ((self.error_component_filter, "Todos os componentes"), (self.error_code_filter, "Todos os códigos"), (self.error_class_filter, "Todas as classes")): combo.addItem(label, ""); filters.addWidget(combo)
        self.copy_error_button = QPushButton("Copiar linha selecionada"); filters.addWidget(self.copy_error_button); filters.addStretch(); layout.addLayout(filters)
        self.errors_empty = self._empty("Nenhum erro operacional recente.")
        self.errors = self._table(("Data/hora", "Componente", "Operação", "Código", "Classe", "Mensagem sanitizada", "Ref segura"), 130)
        self.errors.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.errors.setSortingEnabled(True)
        layout.addWidget(self.errors_empty); layout.addWidget(self.errors); self.body_layout.addWidget(section)

    def _build_environment(self) -> None:
        section = QGroupBox("Ambiente"); layout = QVBoxLayout(section); self.environment = self._table(("Item", "Valor"), 180)
        layout.addWidget(self.environment); self.body_layout.addWidget(section)

    @staticmethod
    def _empty(text: str) -> QLabel:
        label = QLabel(text); label.setObjectName("DiagnosticsEmptyState"); return label

    @staticmethod
    def _table(headers: tuple[str, ...], height: int) -> QTableWidget:
        table = QTableWidget(0, len(headers)); table.setHorizontalHeaderLabels(headers); table.setMaximumHeight(height)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); table.setAlternatingRowColors(True); table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents); table.horizontalHeader().setStretchLastSection(True); return table

    def _connect(self) -> None:
        self.refresh_button.clicked.connect(self.refresh); self.run_button.clicked.connect(self.run_diagnostics); self.export_button.clicked.connect(self.export_json)
        self.copy_summary_button.clicked.connect(self.copy_summary); self.copy_error_button.clicked.connect(self.copy_selected_error)
        self.components.itemSelectionChanged.connect(self._show_engine_details); self.status_filter.currentTextChanged.connect(self._refresh_engines); self.engine_filter.currentIndexChanged.connect(self._refresh_engines)
        for combo in (self.error_component_filter, self.error_code_filter, self.error_class_filter): combo.currentIndexChanged.connect(self._refresh_errors)

    def run_diagnostics(self) -> None:
        self.observability.set_components(self.health_checks.run()); self.refresh()

    def refresh(self) -> None:
        snap = self.observability.snapshot(); self._snapshot = snap; self._refresh_cards(snap); self._refresh_case(snap)
        self._sync_combo(self.engine_filter, sorted({row[0] for row in self._engine_data(snap)}), "Todos os componentes")
        self._refresh_engines(); self._refresh_jobs(snap); self._sync_error_filters(snap); self._refresh_errors(); self._refresh_environment(snap)

    def _refresh_cards(self, snap: ObservabilitySnapshot) -> None:
        self.health_badge.set_status(snap.system_health); self.cards["health"].update_value("", STATUS_PRESENTATION[snap.system_health][1], snap.system_health)
        counts = {status: sum(row[2] is status for row in self._engine_data(snap)) for status in OperationalStatus}
        self.cards["engines"].update_value(f"{counts[OperationalStatus.OK]} OK", f"{counts[OperationalStatus.UNAVAILABLE]} indisponíveis · {counts[OperationalStatus.DEGRADED]} degradados · {counts[OperationalStatus.ERROR]} erros", snap.system_health)
        if snap.case_performance and snap.case_performance.total_analysis_ms is not None: perf, detail = format_duration(snap.case_performance.total_analysis_ms), "análise total do Caso"
        else:
            executions = sum(m.executions for m in snap.engine_metrics); total = sum(m.total_duration_ms for m in snap.engine_metrics)
            perf, detail = ((format_duration(total / executions), "média instrumentada") if executions else ("—", "sem duração disponível"))
        self.cards["performance"].update_value(perf, detail)
        errors = len(snap.recent_errors); self.cards["errors"].update_value(format_count(errors, "erro", "erros"), "eventos recentes", OperationalStatus.ERROR if errors else OperationalStatus.OK)
        jobs = len(snap.active_jobs); self.cards["jobs"].update_value(format_count(jobs, "em execução", "em execução"), "jobs ativos", OperationalStatus.DEGRADED if jobs else OperationalStatus.OK)

    def _refresh_case(self, snap: ObservabilitySnapshot) -> None:
        case = snap.case_performance; values = {key: "—" for key in self.case_labels}; counts = None
        if case:
            values = {"case_ref": case.case_ref, "files": str(case.file_count), "size": format_bytes(case.total_size_bytes), "ingestion": format_duration(case.ingestion_ms), "first": format_duration(case.first_result_ms), "total": format_duration(case.total_analysis_ms), "cache": f"{case.cache_hits} hits · {case.cache_misses} misses"}
            counts = {key: getattr(case, key) for key in ("completed", "partial", "failed", "pending", "running")}
        for key, value in values.items(): self.case_labels[key].setText(value)
        self.file_distribution.update_counts(counts)

    def _engine_data(self, snap: ObservabilitySnapshot):
        metrics = {m.engine_id: m for m in snap.engine_metrics}; rows = []
        for component in snap.components:
            metric = metrics.pop(component.component_id, None)
            state = (
                metric.status
                if metric is not None and STATUS_PRIORITY[metric.status] < STATUS_PRIORITY[component.status]
                else component.status
            )
            rows.append((component.component_id, component.display_name, state, component.version, component.last_check, component.message, metric))
        for metric in metrics.values(): rows.append((metric.engine_id, metric.engine_id, metric.status, None, metric.last_execution_at, None, metric))
        return sorted(rows, key=lambda row: (STATUS_PRIORITY[row[2]], row[1].casefold(), row[0]))

    def _refresh_engines(self) -> None:
        if self._snapshot is None: return
        selected = self._selected_key(self.components); status = self.status_filter.currentText(); engine = self.engine_filter.currentData(); rows = []
        self._engine_rows = {}
        for raw in self._engine_data(self._snapshot):
            key, name, state, version, checked, message, metric = raw
            if (status != "Todos os estados" and state.value != status) or (engine and key != engine): continue
            self._engine_rows[key] = raw; last = metric.last_execution_at if metric else checked
            rows.append((key, (name, NumericItem(self._status_text(state), STATUS_PRIORITY[state]), version or "—", self._datetime(last), self._num_duration(metric.average_duration_ms) if metric else "—", self._num_duration(metric.last_duration_ms) if metric else "—", NumericItem(str(metric.executions), metric.executions) if metric else NumericItem("0", 0), NumericItem(str(metric.failures), metric.failures) if metric else NumericItem("0", 0), self._num_duration(metric.total_duration_ms) if metric else "—"), state))
        self._replace_table(self.components, rows, selected); self.engine_chart.update_metrics(self._snapshot.engine_metrics)
        if self._engine_initial_sort:
            self.components.sortItems(1, Qt.SortOrder.AscendingOrder); self._engine_initial_sort = False

    def _refresh_jobs(self, snap: ObservabilitySnapshot) -> None:
        now = datetime.now().astimezone(); rows = [(job.job_id, (job.file_ref or "—", f"{job.engine_id or '—'} / {job.operation or '—'}", job.state.value, self._datetime(job.started_at), format_duration((now-job.started_at.astimezone()).total_seconds()*1000), f"{job.progress_percent}%" if job.progress_percent is not None else "Executando"), None) for job in sorted(snap.active_jobs, key=lambda item: item.started_at)]
        self._replace_table(self.jobs, rows); self.jobs_empty.setVisible(not rows); self.jobs.setVisible(bool(rows))

    def _sync_error_filters(self, snap: ObservabilitySnapshot) -> None:
        self._sync_combo(self.error_component_filter, sorted({e.component_id for e in snap.recent_errors}), "Todos os componentes")
        self._sync_combo(self.error_code_filter, sorted({e.error_code for e in snap.recent_errors}), "Todos os códigos")
        self._sync_combo(self.error_class_filter, sorted({e.exception_class for e in snap.recent_errors}), "Todas as classes")

    def _refresh_errors(self) -> None:
        if self._snapshot is None: return
        selected = self._selected_key(self.errors); component = self.error_component_filter.currentData(); code = self.error_code_filter.currentData(); exception = self.error_class_filter.currentData(); rows = []
        for index, error in enumerate(reversed(self._snapshot.recent_errors)):
            if (component and error.component_id != component) or (code and error.error_code != code) or (exception and error.exception_class != exception): continue
            ref = " / ".join(value for value in (error.case_ref, error.file_ref) if value) or "—"
            rows.append((f"{error.timestamp.isoformat()}:{index}", (self._datetime(error.timestamp), error.component_id, error.operation or "—", error.error_code, error.exception_class, error.message, ref), OperationalStatus.ERROR))
        self._replace_table(self.errors, rows, selected); self.errors_empty.setVisible(not rows); self.errors.setVisible(bool(rows))

    def _refresh_environment(self, snap: ObservabilitySnapshot) -> None:
        env = snap.environment; components = {c.component_id: c for c in snap.components}
        values = (("ForensiHash", env.forensihash_version), ("OS", env.os), ("Arquitetura", env.architecture), ("CPU", env.cpu), ("RAM", format_bytes(env.ram_bytes)), ("Disco disponível", format_bytes(env.disk_available_bytes)), ("Python runtime", env.python_runtime), ("Rust Core", self._dependency(components.get("rust_core"), env.rust_core_version)), ("ExifTool", self._dependency(components.get("exiftool"))), ("Tesseract", self._dependency(components.get("tesseract"))), ("Poppler", self._dependency(components.get("poppler"))))
        self._replace_table(self.environment, [(key, (key, value), None) for key, value in values])

    @staticmethod
    def _dependency(component, version=None):
        if component is None: return "—"
        return DiagnosticsPage._status_text(component.status) + (f" · {version}" if version else "")

    def _replace_table(self, table, rows, selected=None) -> None:
        signature = tuple((key, tuple(value.text() if isinstance(value, QTableWidgetItem) else str(value) for value in values)) for key, values, _ in rows)
        if table.property("dataSignature") == signature: return
        scroll = table.verticalScrollBar().value(); sorting = table.isSortingEnabled(); table.setSortingEnabled(False); table.setRowCount(len(rows))
        for row_index, (key, values, status) in enumerate(rows):
            for column, value in enumerate(values):
                item = value if isinstance(value, QTableWidgetItem) else QTableWidgetItem(str(value)); item.setData(Qt.ItemDataRole.UserRole, key)
                if status is not None and column in (0, 1): item.setForeground(self._status_color(status))
                table.setItem(row_index, column, item)
        table.setProperty("dataSignature", signature); table.setSortingEnabled(sorting); table.verticalScrollBar().setValue(scroll)
        if selected:
            for row in range(table.rowCount()):
                if table.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected: table.selectRow(row); break

    def _show_engine_details(self) -> None:
        raw = self._engine_rows.get(self._selected_key(self.components) or "")
        if not raw: self.engine_details.setText("Selecione um componente para ver detalhes operacionais."); return
        key, name, state, version, checked, message, metric = raw
        details = (("component_id", key), ("display_name", name), ("status", self._status_text(state)), ("version", version or "—"), ("last_check", self._datetime(checked)), ("last_execution", self._datetime(metric.last_execution_at) if metric else "—"), ("executions", metric.executions if metric else 0), ("failures", metric.failures if metric else 0), ("average_duration", format_duration(metric.average_duration_ms) if metric else "—"), ("last_duration", format_duration(metric.last_duration_ms) if metric else "—"), ("total_duration", format_duration(metric.total_duration_ms) if metric else "—"), ("message", message or "—"), ("dependency_state", self._status_text(state)), ("operations", "—"))
        self.engine_details.setText("   ·   ".join(f"{label}: {value}" for label, value in details))

    def copy_summary(self) -> str:
        snap = self._snapshot or self.observability.snapshot(); counts = {status: sum(row[2] is status for row in self._engine_data(snap)) for status in OperationalStatus}
        lines = [f"ForensiHash {snap.environment.forensihash_version}", f"Status geral: {self._status_text(snap.system_health)}", f"Componentes: {counts[OperationalStatus.OK]} OK; {counts[OperationalStatus.DEGRADED]} degradados; {counts[OperationalStatus.UNAVAILABLE]} indisponíveis; {counts[OperationalStatus.ERROR]} erros", f"Jobs ativos: {len(snap.active_jobs)}", f"Erros recentes: {len(snap.recent_errors)}"]
        if snap.case_performance:
            case = snap.case_performance; lines.append(f"Caso/ref: {case.case_ref}; arquivos: {case.file_count}; análise total: {format_duration(case.total_analysis_ms)}; cache: {case.cache_hits} hits/{case.cache_misses} misses")
        text = "\n".join(lines); QApplication.clipboard().setText(text); return text

    def copy_selected_error(self) -> str | None:
        row = self.errors.currentRow()
        if row < 0: return None
        text = " | ".join(self.errors.item(row, column).text() for column in range(self.errors.columnCount())); QApplication.clipboard().setText(text); return text

    def export_json(self) -> None:
        default = f"forensihash-diagnostic-{datetime.now():%Y%m%d-%H%M%S}.json"; filename, _ = QFileDialog.getSaveFileName(self, "Exportar diagnóstico", default, "JSON (*.json)")
        if filename:
            try: export_diagnostic(self.observability.snapshot(), Path(filename))
            except OSError as error: QMessageBox.warning(self, "Exportação", f"Não foi possível exportar: {type(error).__name__}")

    @staticmethod
    def _sync_combo(combo, values, label) -> None:
        if [combo.itemData(index) for index in range(1, combo.count())] == values: return
        current = combo.currentData(); combo.blockSignals(True); combo.clear(); combo.addItem(label, "")
        for value in values: combo.addItem(value, value)
        combo.setCurrentIndex(max(0, combo.findData(current))); combo.blockSignals(False)

    @staticmethod
    def _selected_key(table) -> str | None:
        item = table.item(table.currentRow(), 0) if table.currentRow() >= 0 else None; value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return str(value) if value else None

    @staticmethod
    def _datetime(value): return value.astimezone().strftime("%d/%m/%Y %H:%M:%S") if value else "—"

    @staticmethod
    def _status_text(status):
        icon, text, _ = STATUS_PRESENTATION[status]; return f"{icon} {text}"

    @staticmethod
    def _status_color(status): return QColor({OperationalStatus.OK: "#58d68d", OperationalStatus.DEGRADED: "#f4c95d", OperationalStatus.UNAVAILABLE: "#8da2b8", OperationalStatus.ERROR: "#ff6b6b"}[status])

    @staticmethod
    def _num_duration(value): return NumericItem(format_duration(value), value)

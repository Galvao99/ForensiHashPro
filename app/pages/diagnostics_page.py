from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QApplication,
    QComboBox,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.observability import HealthCheckService, ObservabilityService, export_diagnostic
from app.observability.models import ObservabilitySnapshot, OperationalStatus
from app.presentation.diagnostics_formatting import format_bytes, format_count, format_duration
from app.widgets.diagnostics import (
    DiagnosticsMetricCard,
    EngineTimeChart,
    FileStatusDistribution,
    OperationalStatusBadge,
    ResponsiveMetricGrid,
    STATUS_PRESENTATION,
)

STATUS_PRIORITY = {
    OperationalStatus.ERROR: 0,
    OperationalStatus.DEGRADED: 1,
    OperationalStatus.UNAVAILABLE: 2,
    OperationalStatus.OK: 3,
}


class NumericItem(QTableWidgetItem):
    def __init__(self, display: str, value: float | None) -> None:
        super().__init__(display)
        self.value = value
        self.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

    def __lt__(self, other: QTableWidgetItem) -> bool:
        other_value = getattr(other, "value", None)
        return (self.value if self.value is not None else -1) < (
            other_value if other_value is not None else -1
        )


class DiagnosticsPage(QWidget):
    """Dashboard operacional local; apresenta snapshots sem executar análise."""

    def __init__(
        self, observability: ObservabilityService, health_checks: HealthCheckService
    ) -> None:
        super().__init__()
        self.observability = observability
        self.health_checks = health_checks
        self._snapshot: ObservabilitySnapshot | None = None
        self._engine_rows = {}
        self._engine_initial_sort = True
        self.setObjectName("DiagnosticsPage")
        self._build_ui()
        self._connect()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1500)
        self.refresh()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        heading = QLabel("Diagnóstico")
        heading.setObjectName("DiagnosticsTitle")
        subtitle = QLabel("Estado operacional e desempenho da instalação atual.")
        subtitle.setObjectName("DiagnosticsSubtitle")
        subtitle.setWordWrap(True)
        self.snapshot_status = QLabel()
        self.snapshot_status.setObjectName("DiagnosticsCoverageLabel")
        root.addWidget(heading)
        root.addWidget(subtitle)
        root.addWidget(self.snapshot_status)
        actions = QGridLayout()
        self.status_filter = QComboBox()
        self.status_filter.addItems(("Todos os estados", "ERROR", "DEGRADED", "UNAVAILABLE", "OK"))
        self.engine_filter = QComboBox()
        self.engine_filter.addItem("Todos os componentes", "")
        self.refresh_button = QPushButton("Atualizar")
        self.run_button = QPushButton("Executar diagnóstico")
        self.copy_summary_button = QPushButton("Copiar resumo")
        self.export_button = QPushButton("Exportar JSON")
        for index, widget in enumerate(
            (
                self.status_filter,
                self.engine_filter,
                self.refresh_button,
                self.run_button,
                self.copy_summary_button,
                self.export_button,
            )
        ):
            widget.setMinimumWidth(0)
            widget.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            actions.addWidget(widget, index // 3, index % 3)
        for column in range(3):
            actions.setColumnStretch(column, 1)
        root.addLayout(actions)
        self.tabs = QTabWidget()
        self.tabs.setObjectName("DiagnosticsSections")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        root.addWidget(self.tabs)
        for title, builders in (
            ("Visão geral", (self._build_cards, self._build_case)),
            ("Performance", (self._build_performance,)),
            ("Engines", (self._build_engines,)),
            ("Jobs", (self._build_jobs,)),
            ("Erros", (self._build_errors,)),
            ("Ambiente", (self._build_environment,)),
        ):
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setMinimumWidth(0)
            scroll.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
            body = QWidget()
            body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
            self.body_layout = QVBoxLayout(body)
            self.body_layout.setContentsMargins(8, 8, 8, 8)
            self.body_layout.setSpacing(10)
            for builder in builders:
                builder()
            self.body_layout.addStretch()
            scroll.setWidget(body)
            self.tabs.addTab(scroll, title)
        for label in self.findChildren(QLabel):
            label.setTextFormat(Qt.TextFormat.PlainText)

    def _build_cards(self) -> None:
        self.cards = {}
        for index, (key, title) in enumerate(
            (
                ("health", "Status geral"),
                ("engines", "Engines disponíveis"),
                ("performance", "Caso atual"),
                ("errors", "Erros recentes"),
                ("jobs", "Jobs ativos"),
                ("cache", "Cache"),
                ("last", "Última análise"),
            )
        ):
            card = DiagnosticsMetricCard(title)
            self.cards[key] = card
        self.health_badge = OperationalStatusBadge()
        self.cards["health"].layout().insertWidget(1, self.health_badge)
        self.cards["health"].value.setVisible(False)
        self.card_labels = {key: card.value for key, card in self.cards.items()}
        self.body_layout.addWidget(ResponsiveMetricGrid(list(self.cards.values()), max_columns=4))

    def _build_case(self) -> None:
        self.case = QGroupBox("Performance do Caso atual")
        box = QVBoxLayout(self.case)
        facts = []
        self.case_labels = {}
        for index, (key, title) in enumerate(
            (
                ("case_ref", "Caso/ref"),
                ("files", "Arquivos"),
                ("size", "Tamanho total"),
                ("ingestion", "Ingestão"),
                ("first", "Primeiro resultado"),
                ("total", "Análise total"),
                ("cache", "Cache"),
            )
        ):
            frame = QFrame()
            frame.setObjectName("DiagnosticsFact")
            layout = QVBoxLayout(frame)
            layout.setContentsMargins(10, 7, 10, 7)
            caption = QLabel(title)
            caption.setObjectName("DiagnosticsFactTitle")
            value = QLabel("—")
            value.setObjectName("DiagnosticsFactValue")
            caption.setWordWrap(True)
            value.setWordWrap(True)
            value.setTextFormat(Qt.TextFormat.PlainText)
            layout.addWidget(caption)
            layout.addWidget(value)
            facts.append(frame)
            self.case_labels[key] = value
        box.addWidget(ResponsiveMetricGrid(facts))
        self.file_distribution = FileStatusDistribution()
        box.addWidget(self.file_distribution)
        self.body_layout.addWidget(self.case)

    def _build_engines(self) -> None:
        section = QGroupBox("Engines e dependências")
        layout = QVBoxLayout(section)
        self.components = self._table(
            (
                "Componente",
                "Status",
                "Calls",
                "Wall total",
                "CPU total",
                "Avg",
                "Median",
                "Max",
                "Falhas",
                "Canceladas",
                "Cache H/M",
            ),
            320,
        )
        self.components.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.components.setSortingEnabled(True)
        layout.addWidget(self.components)
        self.engine_details = QLabel("Selecione um componente para ver detalhes operacionais.")
        self.engine_details.setObjectName("DiagnosticsDetails")
        self.engine_details.setWordWrap(True)
        layout.addWidget(self.engine_details)
        title = QLabel("Engines mais demoradas nesta execução · top 5")
        title.setObjectName("CardTitle")
        title.setWordWrap(True)
        title.setMinimumWidth(0)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(title)
        self.engine_chart = EngineTimeChart()
        layout.addWidget(self.engine_chart)
        self.body_layout.addWidget(section)

    def _build_performance(self) -> None:
        section = QGroupBox("Performance do Caso")
        layout = QVBoxLayout(section)
        self.performance_empty = self._empty("Nenhuma sessão de performance disponível.")
        layout.addWidget(self.performance_empty)
        self.performance_labels = {}
        for index, (key, title) in enumerate(
            (
                ("ttfr", "TTFR"),
                ("total", "Tempo total"),
                ("files", "Arquivos processados"),
                ("bytes", "Bytes do Caso"),
                ("jobs", "Jobs"),
                ("cache", "Cache hit rate"),
                ("peak", "Pico de concorrência"),
                ("correlation", "Correlação"),
            )
        ):
            card = DiagnosticsMetricCard(title)
            self.performance_labels[key] = card
        layout.addWidget(ResponsiveMetricGrid(list(self.performance_labels.values())))
        self.session_summary = QLabel()
        self.session_summary.setObjectName("DiagnosticsDetails")
        self.session_summary.setWordWrap(True)
        layout.addWidget(self.session_summary)
        self.io_summary = QLabel("I/O medido: indisponível")
        self.io_summary.setObjectName("DiagnosticsDetails")
        self.io_summary.setWordWrap(True)
        layout.addWidget(self.io_summary)
        self.queue_summary = QLabel("Fila: nenhuma sessão")
        self.queue_summary.setObjectName("DiagnosticsDetails")
        self.queue_summary.setWordWrap(True)
        layout.addWidget(self.queue_summary)
        self.correlation_summary = QLabel("Correlação: indisponível")
        self.correlation_summary.setObjectName("DiagnosticsDetails")
        self.correlation_summary.setWordWrap(True)
        layout.addWidget(self.correlation_summary)
        artifact_title = QLabel("Artefatos mais demorados nesta execução")
        artifact_title.setObjectName("CardTitle")
        artifact_title.setWordWrap(True)
        artifact_title.setMinimumWidth(0)
        artifact_title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(artifact_title)
        self.artifacts = self._table(
            ("Artefato/ref", "Total wall", "Etapa mais demorada", "Bytes", "Engines", "Status"), 260
        )
        self.artifacts.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.artifacts)
        self.artifact_details = QLabel("Selecione um artefato para ver as etapas medidas.")
        self.artifact_details.setObjectName("DiagnosticsDetails")
        self.artifact_details.setWordWrap(True)
        layout.addWidget(self.artifact_details)
        self.slowest_operations = QLabel()
        self.slowest_operations.setObjectName("DiagnosticsDetails")
        self.slowest_operations.setWordWrap(True)
        layout.addWidget(self.slowest_operations)
        self.milestones = self._table(("Marco da sessão", "Tempo desde o início"), 190)
        layout.addWidget(self.milestones)
        self.rule_timings = self._table(
            ("Regra de correlação", "Duração", "Findings", "Falhas"), 160
        )
        layout.addWidget(self.rule_timings)
        self.body_layout.addWidget(section)

    def _build_jobs(self) -> None:
        section = QGroupBox("Jobs ativos")
        layout = QVBoxLayout(section)
        self.jobs_empty = self._empty("Nenhum job ativo.")
        self.jobs = self._table(
            ("Arquivo/ref", "Engine/operação", "Estado", "Início", "Duração", "Progresso"), 110
        )
        layout.addWidget(self.jobs_empty)
        layout.addWidget(self.jobs)
        self.body_layout.addWidget(section)

    def _build_errors(self) -> None:
        section = QGroupBox("Erros operacionais recentes")
        layout = QVBoxLayout(section)
        filters = QGridLayout()
        self.error_component_filter = QComboBox()
        self.error_code_filter = QComboBox()
        self.error_class_filter = QComboBox()
        for index, (combo, label) in enumerate(
            (
                (self.error_component_filter, "Todos os componentes"),
                (self.error_code_filter, "Todos os códigos"),
                (self.error_class_filter, "Todas as classes"),
            )
        ):
            combo.addItem(label, "")
            combo.setMinimumWidth(0)
            combo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
            filters.addWidget(combo, index // 2, index % 2)
        self.copy_error_button = QPushButton("Copiar linha selecionada")
        filters.addWidget(self.copy_error_button, 1, 1)
        layout.addLayout(filters)
        self.errors_empty = self._empty("Nenhum erro operacional recente.")
        self.errors = self._table(
            (
                "Data/hora",
                "Componente",
                "Operação",
                "Código",
                "Classe",
                "Mensagem sanitizada",
                "Ref segura",
            ),
            130,
        )
        self.errors.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.errors.setSortingEnabled(True)
        layout.addWidget(self.errors_empty)
        layout.addWidget(self.errors)
        self.body_layout.addWidget(section)

    def _build_environment(self) -> None:
        section = QGroupBox("Ambiente")
        layout = QVBoxLayout(section)
        self.environment = self._table(("Item", "Valor"), 480)
        layout.addWidget(self.environment)
        self.body_layout.addWidget(section)

    @staticmethod
    def _empty(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DiagnosticsEmptyState")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _table(headers: tuple[str, ...], height: int) -> QTableWidget:
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setMaximumHeight(height)
        table.setMinimumWidth(0)
        table.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        table.setMinimumHeight(min(height, 160))
        table.verticalHeader().setDefaultSectionSize(30)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        table.horizontalHeader().setDefaultSectionSize(120)
        table.horizontalHeader().setStretchLastSection(True)
        for index, title in enumerate(headers):
            table.setColumnWidth(
                index,
                max(110, table.horizontalHeader().fontMetrics().horizontalAdvance(title) + 38),
            )
        table.setColumnWidth(0, max(190, table.columnWidth(0)))
        return table

    def _connect(self) -> None:
        self.refresh_button.clicked.connect(self.refresh)
        self.run_button.clicked.connect(self.run_diagnostics)
        self.export_button.clicked.connect(self.export_json)
        self.copy_summary_button.clicked.connect(self.copy_summary)
        self.copy_error_button.clicked.connect(self.copy_selected_error)
        self.components.itemSelectionChanged.connect(self._show_engine_details)
        self.status_filter.currentTextChanged.connect(self._refresh_engines)
        self.engine_filter.currentIndexChanged.connect(self._refresh_engines)
        self.artifacts.itemSelectionChanged.connect(self._show_artifact_details)
        for combo in (self.error_component_filter, self.error_code_filter, self.error_class_filter):
            combo.currentIndexChanged.connect(self._refresh_errors)

    def run_diagnostics(self) -> None:
        self.observability.set_components(self.health_checks.run())
        self.refresh()

    def refresh(self) -> None:
        snap = self.observability.snapshot()
        self._snapshot = snap
        age_seconds = max(0.0, (datetime.now(timezone.utc) - snap.generated_at).total_seconds())
        self.snapshot_status.setText(
            f"Snapshot obsoleto · {age_seconds:.0f} s desde a geração"
            if age_seconds > 5
            else "Snapshot atualizado"
        )
        self._refresh_cards(snap)
        self._refresh_case(snap)
        self._sync_combo(
            self.engine_filter,
            sorted({row[0] for row in self._engine_data(snap)}),
            "Todos os componentes",
        )
        self._refresh_engines()
        self._refresh_performance(snap)
        self._refresh_jobs(snap)
        self._sync_error_filters(snap)
        self._refresh_errors()
        self._refresh_environment(snap)

    def _refresh_cards(self, snap: ObservabilitySnapshot) -> None:
        self.health_badge.set_status(snap.system_health)
        self.cards["health"].update_value(
            "", STATUS_PRESENTATION[snap.system_health][1], snap.system_health
        )
        counts = {
            status: sum(row[2] is status for row in self._engine_data(snap))
            for status in OperationalStatus
        }
        self.cards["engines"].update_value(
            f"{counts[OperationalStatus.OK]} OK",
            f"{counts[OperationalStatus.UNAVAILABLE]} indisponíveis · {counts[OperationalStatus.DEGRADED]} degradados · {counts[OperationalStatus.ERROR]} erros",
            snap.system_health,
        )
        self.cards["performance"].update_value(
            snap.case_performance.case_ref if snap.case_performance else "—",
            "referência pseudonimizada",
        )
        errors = len(snap.recent_errors)
        self.cards["errors"].update_value(
            format_count(errors, "erro", "erros"),
            "eventos recentes",
            OperationalStatus.ERROR if errors else OperationalStatus.OK,
        )
        jobs = len(snap.active_jobs)
        self.cards["jobs"].update_value(
            format_count(jobs, "em execução", "em execução"),
            "jobs ativos",
            OperationalStatus.DEGRADED if jobs else OperationalStatus.OK,
        )
        cache = snap.cache_stats[0] if snap.cache_stats else None
        rate = (
            f"{cache.hit_rate * 100:.1f}%".replace(".", ",")
            if cache and cache.hit_rate is not None
            else "—"
        )
        self.cards["cache"].update_value(
            rate, f"{cache.hits} hits · {cache.misses} misses" if cache else "sem sessão"
        )
        case = snap.case_performance
        self.cards["last"].update_value(
            self._datetime(case.case_finished_at) if case else "—",
            self._session_state(case) if case else "sem análise",
        )

    def _refresh_case(self, snap: ObservabilitySnapshot) -> None:
        case = snap.case_performance
        values = {key: "—" for key in self.case_labels}
        counts = None
        if case:
            values = {
                "case_ref": case.case_ref,
                "files": str(case.file_count),
                "size": format_bytes(case.total_size_bytes),
                "ingestion": format_duration(case.ingestion_ms),
                "first": format_duration(case.first_result_ms),
                "total": format_duration(case.total_analysis_ms),
                "cache": f"{case.cache_hits} hits · {case.cache_misses} misses",
            }
            counts = {
                key: getattr(case, key)
                for key in ("completed", "partial", "failed", "pending", "running")
            }
        for key, value in values.items():
            self.case_labels[key].setText(value)
        self.file_distribution.update_counts(counts)

    def _engine_data(self, snap: ObservabilitySnapshot):
        metrics = {m.engine_id: m for m in snap.engine_metrics}
        rows = []
        for component in snap.components:
            metric = metrics.pop(component.component_id, None)
            state = (
                metric.status
                if metric is not None
                and STATUS_PRIORITY[metric.status] < STATUS_PRIORITY[component.status]
                else component.status
            )
            rows.append(
                (
                    component.component_id,
                    component.display_name,
                    state,
                    component.version,
                    component.last_check,
                    component.message,
                    metric,
                )
            )
        for metric in metrics.values():
            if metric.engine_id in {"analysis_pipeline", "analysis_cache"}:
                continue
            rows.append(
                (
                    metric.engine_id,
                    metric.engine_id,
                    metric.status,
                    None,
                    metric.last_execution_at,
                    None,
                    metric,
                )
            )
        return sorted(rows, key=lambda row: (STATUS_PRIORITY[row[2]], row[1].casefold(), row[0]))

    def _refresh_engines(self) -> None:
        if self._snapshot is None:
            return
        selected = self._selected_key(self.components)
        status = self.status_filter.currentText()
        engine = self.engine_filter.currentData()
        rows = []
        self._engine_rows = {}
        for raw in self._engine_data(self._snapshot):
            key, name, state, version, checked, message, metric = raw
            if (status != "Todos os estados" and state.value != status) or (
                engine and key != engine
            ):
                continue
            self._engine_rows[key] = raw
            rows.append(
                (
                    key,
                    (
                        name,
                        NumericItem(self._status_text(state), STATUS_PRIORITY[state]),
                        NumericItem(str(metric.executions), metric.executions) if metric else "—",
                        self._num_duration(metric.total_duration_ms) if metric else "—",
                        self._num_duration(metric.cpu_total_ms)
                        if metric and metric.cpu_total_ms is not None
                        else "Indisponível",
                        self._num_duration(metric.average_duration_ms) if metric else "—",
                        self._num_duration(metric.median_duration_ms) if metric else "—",
                        self._num_duration(metric.maximum_duration_ms) if metric else "—",
                        NumericItem(str(metric.failures), metric.failures) if metric else "—",
                        NumericItem(str(metric.cancelled), metric.cancelled) if metric else "—",
                        f"{metric.cache_hits}/{metric.cache_misses}"
                        if metric and metric.cache_hits + metric.cache_misses
                        else "—",
                    ),
                    state,
                )
            )
        self._replace_table(self.components, rows, selected)
        self.engine_chart.update_metrics(self._snapshot.engine_metrics)
        self._show_engine_details()
        if self._engine_initial_sort:
            self.components.sortItems(1, Qt.SortOrder.AscendingOrder)
            self._engine_initial_sort = False

    def _refresh_performance(self, snap: ObservabilitySnapshot) -> None:
        case = snap.case_performance
        self.performance_empty.setVisible(case is None)
        if case is None:
            for card in self.performance_labels.values():
                card.update_value("—", "indisponível")
            self.session_summary.setText("Métricas indisponíveis até iniciar uma análise.")
        else:
            processed = case.completed + case.partial + case.failed
            jobs = (
                snap.queue_stats.completed_jobs
                + snap.queue_stats.failed_jobs
                + snap.queue_stats.cancelled_jobs
            )
            cache = snap.cache_stats[0] if snap.cache_stats else None
            self.performance_labels["ttfr"].update_value(
                format_duration(case.first_result_ms), "primeiro resultado técnico útil"
            )
            self.performance_labels["total"].update_value(
                format_duration(
                    case.total_analysis_ms
                    if case.total_analysis_ms is not None
                    else case.elapsed_wall_ms
                ),
                self._session_state(case),
            )
            self.performance_labels["files"].update_value(str(processed), f"de {case.file_count}")
            self.performance_labels["bytes"].update_value(
                format_bytes(case.total_size_bytes), "tamanho lógico"
            )
            self.performance_labels["jobs"].update_value(str(jobs), "concluídos/falhos/cancelados")
            hit_rate = (
                f"{cache.hit_rate * 100:.1f}%".replace(".", ",")
                if cache and cache.hit_rate is not None
                else "—"
            )
            self.performance_labels["cache"].update_value(
                hit_rate, f"{cache.hits} hits · {cache.misses} misses" if cache else "indisponível"
            )
            self.performance_labels["peak"].update_value(
                str(snap.queue_stats.peak_concurrency), "execuções simultâneas"
            )
            self.performance_labels["correlation"].update_value(
                format_duration(case.correlation_duration_ms), "etapa de Caso"
            )
            self.session_summary.setText(
                f"{self._session_state(case)} · CPU do processo durante a sessão: {format_duration(case.case_cpu_ms)} "
                "(inclui outras threads; não atribuída às engines). "
                f"Cache de resultados em memória: entradas elegíveis no início {cache.entries if cache and cache.entries is not None else 'indisponível'}; evictions indisponível. "
                f"Cobertura de profiling parcial. Amostras detalhadas descartadas pelo limite: {snap.dropped_execution_samples}. "
                "TTFR mede a disponibilidade antes do envio à UI; não inclui a latência de renderização."
            )
        io = snap.io_stats
        if io is None or io.measured_engine_reads is None:
            self.io_summary.setText(
                "I/O medido: indisponível — bibliotecas sem contadores não são estimadas."
            )
        else:
            amplification = (
                f"{io.read_amplification:.2f}x".replace(".", ",")
                if io.read_amplification is not None
                else "—"
            )
            self.io_summary.setText(
                f"Leitura medida parcialmente: {format_bytes(io.measured_engine_reads)} · amplificação mínima observada {amplification} · {io.instrumented_engines} de {io.observed_engines} engines"
            )
        queue = snap.queue_stats
        self.queue_summary.setText(
            "Fila: nenhuma sessão"
            if case is None
            else f"Fila atual {queue.queue_depth} · pico {queue.peak_queue_depth} · execuções ativas {queue.active_executions} · pico de concorrência {queue.peak_concurrency} · concluídas {queue.completed_jobs} · falhas {queue.failed_jobs} · canceladas {queue.cancelled_jobs} · canceladas antes de iniciar {queue.cancelled_before_start}"
        )
        correlation = snap.correlation_stats
        self.correlation_summary.setText(
            "Correlação: indisponível"
            if correlation is None
            else f"Correlação (Case-level): {format_duration(correlation.duration_ms)} · fatos {correlation.facts_processed} · ocorrências {correlation.occurrences_processed} · relações {correlation.relations_generated} · regras {correlation.rules_evaluated} · com findings {correlation.rules_producing_findings} · falhas {correlation.rule_failures} · índice {format_duration(correlation.index_build_duration_ms)} · regras {format_duration(correlation.rule_evaluation_duration_ms)}"
        )
        rows = [
            (
                item.artifact_ref,
                (
                    item.artifact_ref,
                    NumericItem(
                        format_duration(item.total_duration_ms)
                        + (" (parcial)" if item.state.value == "PARTIAL" else ""),
                        item.total_duration_ms,
                    ),
                    f"{item.slowest_stage or '—'} · {format_duration(item.slowest_stage_ms)}",
                    NumericItem(format_bytes(item.size_bytes), item.size_bytes),
                    NumericItem(str(item.engine_count), item.engine_count),
                    item.status.value,
                ),
                None,
            )
            for item in snap.artifact_metrics[:10]
        ]
        selected = self._selected_key(self.artifacts)
        self._replace_table(self.artifacts, rows, selected)
        self._show_artifact_details()
        milestones = {
            "analysis_started": "Análise iniciada",
            "first_parser_completed": "Primeiro parser concluído",
            "first_useful_result": "Primeiro resultado útil disponível",
            "all_artifacts_processed": "Todos os artefatos processados",
            "correlation_started": "Correlação canônica iniciada",
            "correlation_completed": "Correlação canônica concluída",
            "case_complete": "Caso concluído",
            "analysis_cancelled": "Análise cancelada",
        }
        self._replace_table(
            self.milestones,
            [
                (
                    item.name,
                    (milestones.get(item.name, "Marco"), self._num_duration(item.elapsed_ms)),
                    None,
                )
                for item in (case.milestones if case else ())
            ],
        )
        rule_names = {
            "case.identical_calculated_hash": "Hashes calculados idênticos",
            "case.declared_hash_verification": "Verificação de hash declarado",
            "case.signing_time_certificate_validity": "Tempo de assinatura e certificado",
            "case.document_date_metadata_temporal_relation": "Datas documentais e metadados",
        }
        self._replace_table(
            self.rule_timings,
            [
                (
                    item.rule_id,
                    (
                        rule_names.get(item.rule_id, f"Regra {index + 1}"),
                        self._num_duration(item.duration_ms),
                        NumericItem(str(item.findings), item.findings),
                        NumericItem(str(int(item.failed)), int(item.failed)),
                    ),
                    None,
                )
                for index, item in enumerate(correlation.rules if correlation else ())
            ],
        )
        slowest = sorted(
            (
                item
                for item in snap.slowest_executions
                if item.engine_id not in {"analysis_pipeline", "analysis_cache"}
            ),
            key=lambda item: (
                -(item.duration_ms or 0),
                item.engine_id,
                item.file_ref or "",
                item.execution_id,
            ),
        )[:5]
        self.slowest_operations.setText(
            "Operações mais demoradas nesta execução:\n"
            + (
                "\n".join(
                    f"{item.engine_id} · {item.file_ref or 'Etapa do Caso'} · {format_duration(item.duration_ms)}"
                    for item in slowest
                )
                or "Nenhuma operação medida."
            )
        )

    def _refresh_jobs(self, snap: ObservabilitySnapshot) -> None:
        rows = [
            (
                job.job_id,
                (
                    job.file_ref or "—",
                    f"{job.engine_id or '—'} / {job.operation or '—'}",
                    job.state.value,
                    self._datetime(job.started_at),
                    self._num_duration(job.elapsed_ms),
                    f"{job.progress_percent}%"
                    if job.progress_percent is not None
                    else "Executando",
                ),
                None,
            )
            for job in sorted(snap.active_jobs, key=lambda item: item.started_at)
        ]
        self._replace_table(self.jobs, rows)
        self.jobs_empty.setVisible(not rows)
        self.jobs.setVisible(bool(rows))

    def _sync_error_filters(self, snap: ObservabilitySnapshot) -> None:
        self._sync_combo(
            self.error_component_filter,
            sorted({e.component_id for e in snap.recent_errors}),
            "Todos os componentes",
        )
        self._sync_combo(
            self.error_code_filter,
            sorted({e.error_code for e in snap.recent_errors}),
            "Todos os códigos",
        )
        self._sync_combo(
            self.error_class_filter,
            sorted({e.exception_class for e in snap.recent_errors}),
            "Todas as classes",
        )

    def _refresh_errors(self) -> None:
        if self._snapshot is None:
            return
        selected = self._selected_key(self.errors)
        component = self.error_component_filter.currentData()
        code = self.error_code_filter.currentData()
        exception = self.error_class_filter.currentData()
        rows = []
        for index, error in enumerate(reversed(self._snapshot.recent_errors)):
            if (
                (component and error.component_id != component)
                or (code and error.error_code != code)
                or (exception and error.exception_class != exception)
            ):
                continue
            ref = " / ".join(value for value in (error.case_ref, error.file_ref) if value) or "—"
            rows.append(
                (
                    f"{error.timestamp.isoformat()}:{index}",
                    (
                        self._datetime(error.timestamp),
                        error.component_id,
                        error.operation or "—",
                        error.error_code,
                        error.exception_class,
                        error.message,
                        ref,
                    ),
                    OperationalStatus.ERROR,
                )
            )
        self._replace_table(self.errors, rows, selected)
        self.errors_empty.setVisible(not rows)
        self.errors.setVisible(bool(rows))

    def _refresh_environment(self, snap: ObservabilitySnapshot) -> None:
        env = snap.environment
        components = {c.component_id: c for c in snap.components}
        values = (
            ("ForensiHash", env.forensihash_version),
            ("OS", env.os),
            ("Arquitetura", env.architecture),
            ("CPU", env.cpu),
            ("RAM", format_bytes(env.ram_bytes)),
            ("Disco disponível", format_bytes(env.disk_available_bytes)),
            ("Python runtime", env.python_runtime),
            ("Rust Core", self._dependency(components.get("rust_core"), env.rust_core_version)),
            ("ExifTool", self._dependency(components.get("exiftool"))),
            ("Tesseract", self._dependency(components.get("tesseract"))),
            ("Poppler", self._dependency(components.get("poppler"))),
        )
        self._replace_table(self.environment, [(key, (key, value), None) for key, value in values])
        extras = (
            (
                "CPUs lógicas",
                str(env.logical_cpu_count) if env.logical_cpu_count is not None else "—",
            ),
            ("PySide6", env.pyside_version or "—"),
            ("Qt", env.qt_version or "—"),
            ("pyHanko", env.pyhanko_version or "—"),
            ("Build", env.build_identifier or "Indisponível"),
        )
        self._replace_table(
            self.environment, [(key, (key, value), None) for key, value in (*values, *extras)]
        )

    @staticmethod
    def _dependency(component, version=None):
        if component is None:
            return version or "—"
        available_version = version or component.version
        return DiagnosticsPage._status_text(component.status) + (
            f" · {available_version}" if available_version else ""
        )

    def _replace_table(self, table, rows, selected=None) -> None:
        signature = tuple(
            (
                key,
                tuple(
                    value.text() if isinstance(value, QTableWidgetItem) else str(value)
                    for value in values
                ),
            )
            for key, values, _ in rows
        )
        if table.property("dataSignature") == signature:
            return
        scroll = table.verticalScrollBar().value()
        sorting = table.isSortingEnabled()
        table.setSortingEnabled(False)
        table.setRowCount(len(rows))
        for row_index, (key, values, status) in enumerate(rows):
            for column, value in enumerate(values):
                item = (
                    value if isinstance(value, QTableWidgetItem) else QTableWidgetItem(str(value))
                )
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setToolTip(item.text())
                table.setItem(row_index, column, item)
        table.setProperty("dataSignature", signature)
        table.setSortingEnabled(sorting)
        table.verticalScrollBar().setValue(scroll)
        if selected:
            for row in range(table.rowCount()):
                if table.item(row, 0).data(Qt.ItemDataRole.UserRole) == selected:
                    table.selectRow(row)
                    break

    def _show_engine_details(self) -> None:
        raw = self._engine_rows.get(self._selected_key(self.components) or "")
        if not raw:
            self.engine_details.setText("Selecione um componente para ver detalhes operacionais.")
            return
        key, name, state, version, checked, message, metric = raw
        samples = sorted(
            (
                item
                for item in (self._snapshot.slowest_executions if self._snapshot else ())
                if item.engine_id == key and item.duration_ms is not None
            ),
            key=lambda item: (-(item.duration_ms or 0), item.file_ref or "", item.execution_id),
        )[:5]
        slowest = (
            "; ".join(
                f"{item.file_ref or 'case'} — {format_duration(item.duration_ms)}"
                for item in samples
            )
            or "—"
        )
        header = f"{name} · {self._status_text(state)}\n"
        if metric is None:
            measurements = "Nenhuma execução medida nesta sessão."
        else:
            cache = (
                f"{metric.cache_hits} hits / {metric.cache_misses} misses"
                if metric.cache_hits + metric.cache_misses
                else "indisponível para esta engine"
            )
            measurements = (
                f"{metric.executions} execuções · wall acumulado {format_duration(metric.total_duration_ms)} · CPU indisponível\n"
                f"Média {format_duration(metric.average_duration_ms)} · mediana {format_duration(metric.median_duration_ms)} · máximo {format_duration(metric.maximum_duration_ms)}\n"
                f"Falhas {metric.failures} · canceladas {metric.cancelled} · cache: {cache}\n"
                f"Mediana calculada em {metric.median_sample_count} amostras recentes / {metric.timed_executions} execuções medidas.\n"
                f"Mais demoradas nesta execução: {slowest}"
            )
        self.engine_details.setText(
            header
            + measurements
            + f"\ncomponent_id: {key} · versão {version or '—'} · última verificação {self._datetime(checked)}"
        )

    def _show_artifact_details(self) -> None:
        key = self._selected_key(self.artifacts)
        artifact = next(
            (
                item
                for item in (self._snapshot.artifact_metrics if self._snapshot else ())
                if item.artifact_ref == key
            ),
            None,
        )
        if artifact is None:
            self.artifact_details.setText("Selecione um artefato para ver as etapas medidas.")
            return
        stages = "\n".join(
            f"{item.operation or item.engine_id}: {format_duration(item.duration_ms)}"
            for item in artifact.stages
        )
        self.artifact_details.setText(
            f"{artifact.artifact_ref} · Etapas do artefato\n{stages}\nTotal wall: {format_duration(artifact.total_duration_ms)} · Wall acumulado das etapas retidas: {format_duration(artifact.stage_wall_ms)}\nExtração de texto inclui OCR; etapas inclusivas podem se sobrepor. Correlação do Caso não é atribuída ao arquivo."
        )

    def copy_summary(self) -> str:
        snap = self._snapshot or self.observability.snapshot()
        counts = {
            status: sum(row[2] is status for row in self._engine_data(snap))
            for status in OperationalStatus
        }
        lines = [
            f"ForensiHash {snap.environment.forensihash_version}",
            f"Status geral: {self._status_text(snap.system_health)}",
            f"Componentes: {counts[OperationalStatus.OK]} OK; {counts[OperationalStatus.DEGRADED]} degradados; {counts[OperationalStatus.UNAVAILABLE]} indisponíveis; {counts[OperationalStatus.ERROR]} erros",
            f"Jobs ativos: {len(snap.active_jobs)}",
            f"Erros recentes: {len(snap.recent_errors)}",
        ]
        if snap.case_performance:
            case = snap.case_performance
            lines.append(
                f"Caso/ref: {case.case_ref}; arquivos: {case.file_count}; análise total: {format_duration(case.total_analysis_ms)}; cache: {case.cache_hits} hits/{case.cache_misses} misses"
            )
        text = "\n".join(lines)
        QApplication.clipboard().setText(text)
        return text

    def copy_selected_error(self) -> str | None:
        row = self.errors.currentRow()
        if row < 0:
            return None
        text = " | ".join(
            self.errors.item(row, column).text() for column in range(self.errors.columnCount())
        )
        QApplication.clipboard().setText(text)
        return text

    def export_json(self) -> None:
        default = f"forensihash-diagnostic-{datetime.now():%Y%m%d-%H%M%S}.json"
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exportar diagnóstico", default, "JSON (*.json)"
        )
        if not filename:
            return
        try:
            export_diagnostic(self.observability.snapshot(), Path(filename))
        except Exception as error:
            self.observability.record_error(
                component_id="diagnostics",
                operation="export_json",
                error_code="diagnostic_export_failed",
                error=error,
            )
            QMessageBox.warning(
                self,
                "Exportação",
                f"Não foi possível exportar o diagnóstico ({type(error).__name__}).",
            )

    @staticmethod
    def _sync_combo(combo, values, label) -> None:
        if [combo.itemData(index) for index in range(1, combo.count())] == values:
            return
        current = combo.currentData()
        combo.blockSignals(True)
        combo.clear()
        combo.addItem(label, "")
        for value in values:
            combo.addItem(value, value)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        combo.blockSignals(False)

    @staticmethod
    def _selected_key(table) -> str | None:
        item = table.item(table.currentRow(), 0) if table.currentRow() >= 0 else None
        value = item.data(Qt.ItemDataRole.UserRole) if item else None
        return str(value) if value else None

    @staticmethod
    def _datetime(value):
        return value.astimezone().strftime("%d/%m/%Y %H:%M:%S") if value else "—"

    @staticmethod
    def _status_text(status):
        icon, text, _ = STATUS_PRESENTATION[status]
        return f"{icon} {text}"

    @staticmethod
    def _session_state(case):
        return {
            "running": "Análise em andamento — métricas parciais",
            "completed": "Análise concluída",
            "partial": "Análise concluída — resultados parciais",
            "cancelled": "Análise cancelada — métricas parciais",
            "failed": "Análise interrompida por erro — métricas parciais",
        }.get(case.state.value, case.state.value)

    @staticmethod
    def _num_duration(value):
        return NumericItem(format_duration(value), value)

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QProgressBar, QVBoxLayout, QWidget,
)

from app.observability.models import EngineMetric, OperationalStatus
from app.presentation.diagnostics_formatting import format_duration


STATUS_PRESENTATION = {
    OperationalStatus.OK: ("●", "Saudável", "ok"),
    OperationalStatus.DEGRADED: ("▲", "Degradado", "degraded"),
    OperationalStatus.UNAVAILABLE: ("◆", "Indisponível", "unavailable"),
    OperationalStatus.ERROR: ("✕", "Erro", "error"),
}


class OperationalStatusBadge(QLabel):
    def __init__(self) -> None:
        super().__init__(); self.setObjectName("DiagnosticsStatusBadge")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_status(self, status: OperationalStatus) -> None:
        icon, text, kind = STATUS_PRESENTATION[status]
        self.setText(f"{icon}  {text}"); self.setProperty("statusKind", kind)
        self.setAccessibleName(f"Estado operacional: {text}")
        self.style().unpolish(self); self.style().polish(self)


class DiagnosticsMetricCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__(); self.setObjectName("DiagnosticsMetricCard")
        layout = QVBoxLayout(self); layout.setContentsMargins(14, 12, 14, 12); layout.setSpacing(4)
        self.title = QLabel(title); self.title.setObjectName("DiagnosticsCardTitle")
        self.value = QLabel("—"); self.value.setObjectName("DiagnosticsCardValue")
        self.detail = QLabel(""); self.detail.setObjectName("DiagnosticsCardDetail")
        layout.addWidget(self.title); layout.addWidget(self.value); layout.addWidget(self.detail)

    def update_value(self, value: str, detail: str = "", status: OperationalStatus | None = None) -> None:
        self.value.setText(value); self.detail.setText(detail); self.detail.setVisible(bool(detail))
        kind = STATUS_PRESENTATION[status][2] if status is not None else "neutral"
        self.setProperty("statusKind", kind); self.style().unpolish(self); self.style().polish(self)


class EngineTimeChart(QFrame):
    def __init__(self) -> None:
        super().__init__(); self.setObjectName("DiagnosticsChart")
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(12, 10, 12, 10); self.layout.setSpacing(7)
        self.coverage_label = QLabel("Cobertura de métricas parcial")
        self.coverage_label.setObjectName("DiagnosticsCoverageLabel")
        self.layout.addWidget(self.coverage_label); self._rows: list[QWidget] = []

    def update_metrics(self, metrics: tuple[EngineMetric, ...]) -> None:
        ordered = sorted(metrics, key=lambda item: (-item.total_duration_ms, item.engine_id))
        signature = tuple((m.engine_id, m.total_duration_ms) for m in ordered)
        if getattr(self, "_signature", None) == signature:
            return
        self._signature = signature
        for widget in self._rows: widget.deleteLater()
        self._rows.clear()
        total = sum(item.total_duration_ms for item in ordered)
        if not ordered or total <= 0:
            empty = QLabel("Nenhuma duração instrumentada disponível."); empty.setObjectName("DiagnosticsEmptyState")
            self.layout.addWidget(empty); self._rows.append(empty); return
        for metric in ordered:
            row = QWidget(); row_layout = QHBoxLayout(row); row_layout.setContentsMargins(0, 0, 0, 0)
            name = QLabel(metric.engine_id); name.setMinimumWidth(150)
            percent = metric.total_duration_ms / total * 100
            bar = QProgressBar(); bar.setRange(0, 1000); bar.setValue(round(percent * 10)); bar.setTextVisible(False)
            bar.setObjectName("DiagnosticsTimeBar")
            value = QLabel(f"{format_duration(metric.total_duration_ms)}  ·  {percent:.1f}%".replace(".", ",")); value.setMinimumWidth(125)
            row_layout.addWidget(name); row_layout.addWidget(bar, 1); row_layout.addWidget(value)
            self.layout.addWidget(row); self._rows.append(row)


class FileStatusDistribution(QFrame):
    ORDER = (("completed", "Concluídos", "ok"), ("partial", "Parciais", "degraded"),
             ("failed", "Falhas", "error"), ("running", "Em execução", "running"),
             ("pending", "Pendentes", "unavailable"))

    def __init__(self) -> None:
        super().__init__(); self.setObjectName("DiagnosticsChart")
        self.layout = QVBoxLayout(self); self.layout.setContentsMargins(12, 10, 12, 10); self.layout.setSpacing(6)
        self._bars: dict[str, tuple[QLabel, QProgressBar, QLabel]] = {}
        self.empty = QLabel("Nenhum Caso em observação."); self.empty.setObjectName("DiagnosticsEmptyState")
        self.layout.addWidget(self.empty)
        for key, label, kind in self.ORDER:
            row = QWidget(); line = QHBoxLayout(row); line.setContentsMargins(0, 0, 0, 0)
            name = QLabel(label); name.setMinimumWidth(105); bar = QProgressBar(); bar.setRange(0, 1000); bar.setTextVisible(False)
            bar.setObjectName("DiagnosticsStatusBar"); bar.setProperty("statusKind", kind)
            count = QLabel("0"); count.setMinimumWidth(30); line.addWidget(name); line.addWidget(bar, 1); line.addWidget(count)
            self.layout.addWidget(row); self._bars[key] = (row, bar, count)

    def update_counts(self, values: dict[str, int] | None) -> None:
        self.empty.setVisible(values is None)
        total = sum(values.values()) if values else 0
        for key, (row, bar, label) in self._bars.items():
            value = values.get(key, 0) if values else 0; row.setVisible(values is not None)
            bar.setValue(round(value / total * 1000) if total else 0); label.setText(str(value))

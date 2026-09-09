from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class OperationalStatus(str, Enum):
    OK = "OK"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class ExecutionStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    UNAVAILABLE = "unavailable"


class MeasurementState(str, Enum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True, slots=True)
class ExecutionMetric:
    execution_id: str
    engine_id: str
    started_at: datetime
    finished_at: datetime | None = None
    duration_ms: float | None = None
    status: ExecutionStatus = ExecutionStatus.RUNNING
    case_ref: str | None = None
    file_ref: str | None = None
    engine_version: str | None = None
    operation: str | None = None
    error_code: str | None = None
    cache_hit: bool | None = None
    metadata: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)
    cpu_duration_ms: float | None = None
    bytes_read: int | None = None

    def __post_init__(self) -> None:
        if self.started_at.tzinfo is None or (
            self.finished_at is not None and self.finished_at.tzinfo is None
        ):
            raise ValueError("ExecutionMetric timestamps devem conter timezone.")
        duration = self.duration_ms
        if duration is None and self.finished_at is not None:
            duration = max(0.0, (self.finished_at - self.started_at).total_seconds() * 1000)
            object.__setattr__(self, "duration_ms", duration)
        if duration is not None and duration < 0:
            raise ValueError("duration_ms não pode ser negativo.")
        if self.cpu_duration_ms is not None and self.cpu_duration_ms < 0:
            raise ValueError("cpu_duration_ms não pode ser negativo.")
        if self.bytes_read is not None and self.bytes_read < 0:
            raise ValueError("bytes_read não pode ser negativo.")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ComponentHealth:
    component_id: str
    display_name: str
    status: OperationalStatus
    last_check: datetime
    required: bool = False
    version: str | None = None
    message: str | None = None


@dataclass(frozen=True, slots=True)
class EngineMetric:
    engine_id: str
    executions: int
    failures: int
    average_duration_ms: float | None
    last_duration_ms: float | None
    total_duration_ms: float | None
    last_execution_at: datetime
    status: OperationalStatus
    maximum_duration_ms: float | None = None
    median_duration_ms: float | None = None
    cancelled: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cpu_total_ms: float | None = None
    cpu_state: MeasurementState = MeasurementState.UNAVAILABLE
    timed_executions: int = 0
    median_sample_count: int = 0
    state: MeasurementState = MeasurementState.AVAILABLE
    partial: int = 0
    unavailable: int = 0


@dataclass(frozen=True, slots=True)
class ActiveJob:
    job_id: str
    state: ExecutionStatus
    started_at: datetime
    case_ref: str | None = None
    file_ref: str | None = None
    engine_id: str | None = None
    operation: str | None = None
    progress_percent: int | None = None
    elapsed_ms: float | None = None

    def __post_init__(self) -> None:
        if self.progress_percent is not None and not 0 <= self.progress_percent <= 100:
            raise ValueError("progress_percent deve estar entre 0 e 100.")


@dataclass(frozen=True, slots=True)
class OperationalError:
    timestamp: datetime
    component_id: str
    operation: str | None
    error_code: str
    exception_class: str
    message: str
    file_ref: str | None = None
    case_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PerformanceMilestone:
    name: str
    elapsed_ms: float

    def __post_init__(self) -> None:
        if self.elapsed_ms < 0:
            raise ValueError("elapsed_ms não pode ser negativo.")


@dataclass(frozen=True, slots=True)
class CasePerformance:
    case_ref: str
    file_count: int
    total_size_bytes: int
    ingestion_ms: float | None = None
    first_result_ms: float | None = None
    total_analysis_ms: float | None = None
    completed: int = 0
    partial: int = 0
    failed: int = 0
    pending: int = 0
    running: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    session_id: str = ""
    state: ExecutionStatus = ExecutionStatus.RUNNING
    case_cpu_ms: float | None = None
    cpu_state: MeasurementState = MeasurementState.UNAVAILABLE
    peak_concurrency: int = 0
    correlation_duration_ms: float | None = None
    milestones: tuple[PerformanceMilestone, ...] = ()
    case_started_at: datetime | None = None
    first_useful_result_at: datetime | None = None
    case_finished_at: datetime | None = None
    elapsed_wall_ms: float | None = None


@dataclass(frozen=True, slots=True)
class ArtifactMetric:
    artifact_ref: str
    total_duration_ms: float | None
    slowest_stage: str | None
    slowest_stage_ms: float | None
    size_bytes: int | None
    engine_count: int
    status: ExecutionStatus
    stages: tuple[ExecutionMetric, ...] = ()
    state: MeasurementState = MeasurementState.AVAILABLE
    total_is_stage_sum: bool = False
    stage_wall_ms: float = 0.0


@dataclass(frozen=True, slots=True)
class QueueStats:
    queue_depth: int = 0
    peak_queue_depth: int = 0
    active_executions: int = 0
    peak_concurrency: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    cancelled_jobs: int = 0
    cancelled_before_start: int = 0


@dataclass(frozen=True, slots=True)
class CacheStats:
    cache_id: str = "analysis_result_cache"
    hits: int = 0
    misses: int = 0
    entries: int | None = None
    evictions: int | None = None
    state: MeasurementState = MeasurementState.AVAILABLE

    @property
    def hit_rate(self) -> float | None:
        total = self.hits + self.misses
        return self.hits / total if total else None


@dataclass(frozen=True, slots=True)
class CorrelationRuleMetric:
    rule_id: str
    duration_ms: float
    findings: int
    failed: bool = False

    def __post_init__(self) -> None:
        if self.duration_ms < 0:
            raise ValueError("duration_ms não pode ser negativo.")
        if self.findings < 0:
            raise ValueError("findings não pode ser negativo.")


@dataclass(frozen=True, slots=True)
class CorrelationStats:
    facts_processed: int
    occurrences_processed: int
    relations_generated: int
    rules_evaluated: int
    rules_producing_findings: int
    rule_failures: int
    duration_ms: float
    index_build_duration_ms: float
    rule_evaluation_duration_ms: float
    rules: tuple[CorrelationRuleMetric, ...] = ()
    state: MeasurementState = MeasurementState.AVAILABLE

    def __post_init__(self) -> None:
        counts = (
            self.facts_processed,
            self.occurrences_processed,
            self.relations_generated,
            self.rules_evaluated,
            self.rules_producing_findings,
            self.rule_failures,
        )
        durations = (
            self.duration_ms,
            self.index_build_duration_ms,
            self.rule_evaluation_duration_ms,
        )
        if any(value < 0 for value in counts):
            raise ValueError("Contadores de correlação não podem ser negativos.")
        if any(value < 0 for value in durations):
            raise ValueError("Durações de correlação não podem ser negativas.")


@dataclass(frozen=True, slots=True)
class IoStats:
    case_logical_bytes: int
    measured_engine_reads: int | None = None
    temporary_bytes_written: int | None = None
    instrumented_engines: int = 0
    observed_engines: int = 0
    state: MeasurementState = MeasurementState.UNAVAILABLE

    @property
    def read_amplification(self) -> float | None:
        if self.measured_engine_reads is None or self.case_logical_bytes <= 0:
            return None
        return self.measured_engine_reads / self.case_logical_bytes


@dataclass(frozen=True, slots=True)
class EnvironmentSnapshot:
    forensihash_version: str
    os: str
    architecture: str
    cpu: str
    ram_bytes: int | None
    disk_available_bytes: int | None
    python_runtime: str
    rust_core_version: str | None = None
    logical_cpu_count: int | None = None
    pyside_version: str | None = None
    qt_version: str | None = None
    pyhanko_version: str | None = None
    build_identifier: str | None = None


@dataclass(frozen=True, slots=True)
class ObservabilitySnapshot:
    generated_at: datetime
    system_health: OperationalStatus
    components: tuple[ComponentHealth, ...]
    engine_metrics: tuple[EngineMetric, ...]
    recent_errors: tuple[OperationalError, ...]
    active_jobs: tuple[ActiveJob, ...]
    case_performance: CasePerformance | None
    environment: EnvironmentSnapshot
    execution_metrics: tuple[ExecutionMetric, ...] = ()
    artifact_metrics: tuple[ArtifactMetric, ...] = ()
    queue_stats: QueueStats = QueueStats()
    cache_stats: tuple[CacheStats, ...] = ()
    correlation_stats: CorrelationStats | None = None
    io_stats: IoStats | None = None
    dropped_execution_samples: int = 0
    slowest_executions: tuple[ExecutionMetric, ...] = ()
    performance_state: MeasurementState = MeasurementState.UNAVAILABLE

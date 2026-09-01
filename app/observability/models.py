from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
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
    average_duration_ms: float
    last_duration_ms: float
    total_duration_ms: float
    last_execution_at: datetime
    status: OperationalStatus


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

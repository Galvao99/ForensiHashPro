from __future__ import annotations

import os
import platform
import shutil
import sys
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from importlib import metadata as package_metadata
from threading import RLock
from time import perf_counter
from uuid import uuid4

from app.observability.models import (
    ActiveJob, CasePerformance, ComponentHealth, EngineMetric, EnvironmentSnapshot,
    ExecutionMetric, ExecutionStatus, ObservabilitySnapshot, OperationalError,
    OperationalStatus,
)
from app.observability.sanitization import sanitize_message, safe_ref


def aggregate_system_health(components: tuple[ComponentHealth, ...]) -> OperationalStatus:
    required = tuple(item for item in components if item.required)
    if any(item.status is OperationalStatus.ERROR for item in required):
        return OperationalStatus.ERROR
    if any(item.status is OperationalStatus.UNAVAILABLE for item in required):
        return OperationalStatus.ERROR
    if any(item.status is not OperationalStatus.OK for item in required):
        return OperationalStatus.DEGRADED
    if any(item.status in {OperationalStatus.ERROR, OperationalStatus.DEGRADED} for item in components):
        return OperationalStatus.DEGRADED
    return OperationalStatus.OK


class ObservabilityService:
    """Coletor local, bounded e thread-safe; não conhece Qt nem domínio forense."""

    def __init__(self, *, max_metrics: int = 2000, max_errors: int = 200) -> None:
        self._lock = RLock()
        self._metrics: deque[ExecutionMetric] = deque(maxlen=max_metrics)
        self._errors: deque[OperationalError] = deque(maxlen=max_errors)
        self._jobs: dict[str, ActiveJob] = {}
        self._components: tuple[ComponentHealth, ...] = ()
        self._case: CasePerformance | None = None
        self._case_started: float | None = None
        self._environment = collect_environment()

    def begin_case(self, case_id: str, files: list[tuple[str, int]], ingestion_ms: float) -> str:
        case_ref = safe_ref("case", case_id)
        with self._lock:
            self._case_started = perf_counter()
            self._case = CasePerformance(case_ref, len(files), sum(size for _, size in files), ingestion_ms=ingestion_ms, pending=len(files))
        return case_ref

    def update_case(self, *, completed: int, partial: int, failed: int, pending: int,
                    running: int, cache_hits: int, cache_misses: int,
                    first_result: bool = False, finished: bool = False) -> None:
        with self._lock:
            if self._case is None:
                return
            elapsed = (perf_counter() - self._case_started) * 1000 if self._case_started else None
            first = self._case.first_result_ms
            if first_result and first is None:
                first = elapsed
            self._case = replace(self._case, completed=completed, partial=partial,
                failed=failed, pending=pending, running=running, cache_hits=cache_hits,
                cache_misses=cache_misses, first_result_ms=first,
                total_analysis_ms=elapsed if finished else self._case.total_analysis_ms)

    def record_metric(self, metric: ExecutionMetric) -> None:
        with self._lock:
            self._metrics.append(metric)

    def start_job(self, *, case_ref: str | None, file_path: str | None,
                  engine_id: str, operation: str) -> str:
        job_id = str(uuid4())
        job = ActiveJob(job_id, ExecutionStatus.RUNNING, datetime.now(timezone.utc),
                        case_ref, safe_ref("file", file_path) if file_path else None,
                        engine_id, operation)
        with self._lock:
            self._jobs[job_id] = job
        return job_id

    def finish_job(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)

    def record_error(self, *, component_id: str, operation: str | None,
                     error_code: str, error: BaseException | str,
                     file_path: str | None = None, case_ref: str | None = None) -> None:
        event = OperationalError(datetime.now(timezone.utc), component_id, operation,
            error_code, type(error).__name__ if isinstance(error, BaseException) else "OperationalError",
            sanitize_message(error), safe_ref("file", file_path) if file_path else None, case_ref)
        with self._lock:
            self._errors.append(event)

    def set_components(self, components: tuple[ComponentHealth, ...]) -> None:
        with self._lock:
            self._components = tuple(components)

    def snapshot(self) -> ObservabilitySnapshot:
        with self._lock:
            components = self._components
            return ObservabilitySnapshot(datetime.now(timezone.utc), aggregate_system_health(components),
                components, self._aggregate_metrics(), tuple(self._errors), tuple(self._jobs.values()),
                self._case, self._environment)

    def _aggregate_metrics(self) -> tuple[EngineMetric, ...]:
        grouped: dict[str, list[ExecutionMetric]] = {}
        for item in self._metrics:
            if item.duration_ms is not None and item.status is not ExecutionStatus.RUNNING:
                grouped.setdefault(item.engine_id, []).append(item)
        result = []
        for engine_id, items in sorted(grouped.items()):
            total = sum(item.duration_ms or 0 for item in items)
            failures = sum(item.status is ExecutionStatus.FAILED for item in items)
            last = items[-1]
            status = OperationalStatus.ERROR if last.status is ExecutionStatus.FAILED else (OperationalStatus.DEGRADED if last.status is ExecutionStatus.PARTIAL else OperationalStatus.OK)
            result.append(EngineMetric(engine_id, len(items), failures, total / len(items),
                last.duration_ms or 0, total, last.finished_at or last.started_at, status))
        return tuple(result)


def collect_environment() -> EnvironmentSnapshot:
    try:
        version = package_metadata.version("forensihash-pro")
    except package_metadata.PackageNotFoundError:
        version = "0.1.0"
    ram = None
    if hasattr(os, "sysconf"):
        try:
            ram = int(os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES"))
        except (ValueError, OSError, AttributeError):
            ram = None
    try:
        disk = shutil.disk_usage(os.getcwd()).free
    except OSError:
        disk = None
    try:
        core_version = package_metadata.version("forensihash_core")
    except package_metadata.PackageNotFoundError:
        core_version = None
    return EnvironmentSnapshot(version, platform.system(), platform.machine(),
        platform.processor() or "Não informado", ram, disk, platform.python_version(), core_version)

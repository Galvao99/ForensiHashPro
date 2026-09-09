from __future__ import annotations

import os
import platform
import shutil
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from importlib import metadata as package_metadata
from statistics import median
from threading import RLock
from time import perf_counter, process_time
from uuid import uuid4

from app.observability.models import (
    ActiveJob,
    ArtifactMetric,
    CacheStats,
    CasePerformance,
    ComponentHealth,
    CorrelationRuleMetric,
    CorrelationStats,
    EngineMetric,
    EnvironmentSnapshot,
    ExecutionMetric,
    ExecutionStatus,
    IoStats,
    MeasurementState,
    ObservabilitySnapshot,
    OperationalError,
    OperationalStatus,
    PerformanceMilestone,
    QueueStats,
)
from app.observability.sanitization import (
    sanitize_message,
    sanitize_metadata,
    safe_ref,
    safe_identifier,
)


def aggregate_system_health(components: tuple[ComponentHealth, ...]) -> OperationalStatus:
    required = tuple(item for item in components if item.required)
    if any(item.status is OperationalStatus.ERROR for item in required):
        return OperationalStatus.ERROR
    if any(item.status is OperationalStatus.UNAVAILABLE for item in required):
        return OperationalStatus.ERROR
    if any(item.status is not OperationalStatus.OK for item in required):
        return OperationalStatus.DEGRADED
    if any(
        item.status in {OperationalStatus.ERROR, OperationalStatus.DEGRADED} for item in components
    ):
        return OperationalStatus.DEGRADED
    return OperationalStatus.OK


class ObservabilityService:
    """Coletor local, bounded e thread-safe; não conhece Qt nem domínio forense."""

    def __init__(self, *, max_metrics: int = 2000, max_errors: int = 200) -> None:
        self._lock = RLock()
        self._metrics: deque[ExecutionMetric] = deque(maxlen=max_metrics)
        self._errors: deque[OperationalError] = deque(maxlen=max_errors)
        self._jobs: dict[str, ActiveJob] = {}
        self._job_started: dict[str, float] = {}
        self._engine_totals: dict[str, EngineMetric] = {}
        self._duration_samples: dict[str, deque[float]] = {}
        self._slowest: dict[str, tuple[ExecutionMetric, ...]] = {}
        self._dropped_samples = 0
        self._measured_reads: int | None = None
        self._read_engines: set[str] = set()
        self._components: tuple[ComponentHealth, ...] = ()
        self._case: CasePerformance | None = None
        self._case_started: float | None = None
        self._case_cpu_started: float | None = None
        self._queue = QueueStats()
        self._cache_entries: int | None = None
        self._correlation: CorrelationStats | None = None
        self._environment = collect_environment()

    def begin_case(
        self,
        case_id: str,
        files: list[tuple[str, int]],
        ingestion_ms: float,
        *,
        cache_entries: int | None = None,
    ) -> str:
        case_ref = safe_ref("case", case_id)
        with self._lock:
            # One current session; earlier snapshots remain immutable for consumers.
            self._metrics.clear()
            self._engine_totals.clear()
            self._duration_samples.clear()
            self._slowest.clear()
            self._jobs.clear()
            self._job_started.clear()
            self._dropped_samples = 0
            self._measured_reads = None
            self._read_engines.clear()
            self._case_started = perf_counter()
            self._case_cpu_started = process_time()
            self._cache_entries = cache_entries
            self._correlation = None
            self._queue = QueueStats(queue_depth=len(files), peak_queue_depth=len(files))
            self._case = CasePerformance(
                case_ref,
                len(files),
                sum(size for _, size in files),
                ingestion_ms=max(0.0, ingestion_ms),
                pending=len(files),
                session_id=safe_ref("session", uuid4()),
                case_started_at=datetime.now(timezone.utc),
                milestones=(PerformanceMilestone("analysis_started", 0.0),),
            )
        return case_ref

    def update_case(
        self,
        *,
        completed: int,
        partial: int,
        failed: int,
        pending: int,
        running: int,
        cache_hits: int,
        cache_misses: int,
        first_result: bool = False,
        finished: bool = False,
        cancelled: bool = False,
        session_failed: bool = False,
        session_degraded: bool = False,
    ) -> None:
        with self._lock:
            if self._case is None:
                return
            if self._case.state is not ExecutionStatus.RUNNING:
                return
            elapsed = self._elapsed_ms()
            first = self._case.first_result_ms
            if first_result and first is None:
                first = elapsed
                self._mark_milestone("first_useful_result", elapsed)
            if pending == 0 and running == 0 and not cancelled:
                self._mark_milestone("all_artifacts_processed", elapsed)
            if finished or cancelled:
                self._mark_milestone(
                    "analysis_cancelled" if cancelled else "case_complete", elapsed
                )
            final_state = (
                ExecutionStatus.FAILED
                if session_failed
                else ExecutionStatus.CANCELLED
                if cancelled
                else (
                    ExecutionStatus.FAILED
                    if failed and completed + partial == 0
                    else ExecutionStatus.PARTIAL
                    if failed or partial or session_degraded
                    else ExecutionStatus.COMPLETED
                )
                if finished
                else self._case.state
            )
            if finished or cancelled:
                self._queue = replace(
                    self._queue,
                    queue_depth=0,
                    cancelled_before_start=self._queue.queue_depth if cancelled else 0,
                )
            cpu_ms = (
                max(0.0, (process_time() - self._case_cpu_started) * 1000)
                if (finished or cancelled) and self._case_cpu_started is not None
                else self._case.case_cpu_ms
            )
            self._case = replace(
                self._case,
                completed=completed,
                partial=partial,
                failed=failed,
                pending=pending,
                running=running,
                cache_hits=cache_hits,
                cache_misses=cache_misses,
                first_result_ms=first,
                total_analysis_ms=elapsed
                if finished or cancelled
                else self._case.total_analysis_ms,
                state=final_state,
                case_cpu_ms=cpu_ms,
                first_useful_result_at=(
                    datetime.now(timezone.utc)
                    if first_result and self._case.first_useful_result_at is None
                    else self._case.first_useful_result_at
                ),
                case_finished_at=datetime.now(timezone.utc) if finished or cancelled else None,
                elapsed_wall_ms=elapsed,
                cpu_state=MeasurementState.PARTIAL
                if cpu_ms is not None
                else MeasurementState.UNAVAILABLE,
                peak_concurrency=self._queue.peak_concurrency,
                correlation_duration_ms=self._correlation.duration_ms
                if self._correlation
                else None,
            )

    def record_metric(self, metric: ExecutionMetric) -> None:
        with self._lock:
            metric = replace(
                metric,
                metadata=sanitize_metadata(dict(metric.metadata)),
                execution_id=safe_identifier(metric.execution_id),
                engine_id=safe_identifier(metric.engine_id),
                case_ref=safe_identifier(metric.case_ref) if metric.case_ref else None,
                file_ref=safe_identifier(metric.file_ref) if metric.file_ref else None,
                operation=safe_identifier(metric.operation) if metric.operation else None,
                error_code=safe_identifier(metric.error_code) if metric.error_code else None,
            )
            if len(self._metrics) == self._metrics.maxlen:
                self._dropped_samples += 1
            self._metrics.append(metric)
            self._accumulate_engine(metric)
            if metric.bytes_read is not None:
                self._measured_reads = (self._measured_reads or 0) + metric.bytes_read
                if len(self._read_engines) < 128:
                    self._read_engines.add(metric.engine_id)
            if metric.operation == "artifact_parsing" and metric.status in {
                ExecutionStatus.COMPLETED,
                ExecutionStatus.PARTIAL,
            }:
                self._mark_milestone("first_parser_completed", self._elapsed_ms())

    def _accumulate_engine(self, metric: ExecutionMetric) -> None:
        if metric.status is ExecutionStatus.RUNNING:
            return
        engine = metric.engine_id
        if engine not in self._engine_totals and len(self._engine_totals) >= 128:
            self._dropped_samples += 1
            return
        prior = self._engine_totals.get(engine)
        calls = (prior.executions if prior else 0) + 1
        timed = (prior.timed_executions if prior else 0) + int(metric.duration_ms is not None)
        samples = self._duration_samples.setdefault(engine, deque(maxlen=128))
        if metric.duration_ms is not None:
            samples.append(metric.duration_ms)
        total = ((prior.total_duration_ms or 0) if prior else 0) + (metric.duration_ms or 0)
        failures = (prior.failures if prior else 0) + int(
            metric.status is ExecutionStatus.FAILED
        )
        partial = (prior.partial if prior else 0) + int(
            metric.status is ExecutionStatus.PARTIAL
        )
        cancelled = (prior.cancelled if prior else 0) + int(
            metric.status is ExecutionStatus.CANCELLED
        )
        unavailable = (prior.unavailable if prior else 0) + int(
            metric.status is ExecutionStatus.UNAVAILABLE
        )
        status = (
            OperationalStatus.ERROR
            if failures
            else OperationalStatus.UNAVAILABLE
            if unavailable == calls
            else OperationalStatus.DEGRADED
            if partial or cancelled or unavailable
            else OperationalStatus.OK
        )
        cpu = (
            None
            if metric.cpu_duration_ms is None and (prior is None or prior.cpu_total_ms is None)
            else (metric.cpu_duration_ms or 0) + ((prior.cpu_total_ms or 0) if prior else 0)
        )
        self._engine_totals[engine] = EngineMetric(
            engine_id=engine,
            executions=calls,
            failures=failures,
            average_duration_ms=total / timed if timed else None,
            last_duration_ms=metric.duration_ms,
            total_duration_ms=total if timed else None,
            last_execution_at=metric.finished_at or metric.started_at,
            status=status,
            maximum_duration_ms=(
                max(prior.maximum_duration_ms or 0 if prior else 0, metric.duration_ms or 0)
                if timed
                else None
            ),
            median_duration_ms=median(samples) if samples else None,
            cancelled=cancelled,
            cache_hits=(prior.cache_hits if prior else 0)
            + int(metric.cache_hit is True and metric.status is ExecutionStatus.COMPLETED),
            cache_misses=(prior.cache_misses if prior else 0)
            + int(metric.cache_hit is False and metric.status is ExecutionStatus.COMPLETED),
            cpu_total_ms=cpu,
            cpu_state=(
                MeasurementState.PARTIAL if cpu is not None else MeasurementState.UNAVAILABLE
            ),
            timed_executions=timed,
            median_sample_count=len(samples),
            state=MeasurementState.AVAILABLE
            if timed == calls
            else MeasurementState.PARTIAL
            if timed
            else MeasurementState.UNAVAILABLE,
            partial=partial,
            unavailable=unavailable,
        )
        if metric.duration_ms is not None:
            self._slowest[engine] = tuple(
                sorted(
                    (*self._slowest.get(engine, ()), metric),
                    key=lambda item: (
                        -(item.duration_ms or 0),
                        item.file_ref or "",
                        item.execution_id,
                    ),
                )[:5]
            )

    def start_job(
        self, *, case_ref: str | None, file_path: str | None, engine_id: str, operation: str
    ) -> str:
        job_id = str(uuid4())
        job = ActiveJob(
            job_id,
            ExecutionStatus.RUNNING,
            datetime.now(timezone.utc),
            case_ref,
            safe_ref("file", file_path) if file_path else None,
            engine_id,
            operation,
        )
        with self._lock:
            self._jobs[job_id] = job
            self._job_started[job_id] = perf_counter()
            active = len(self._jobs)
            self._queue = replace(
                self._queue,
                queue_depth=max(0, self._queue.queue_depth - 1),
                active_executions=active,
                peak_concurrency=max(self._queue.peak_concurrency, active),
            )
        return job_id

    def finish_job(self, job_id: str, outcome: ExecutionStatus = ExecutionStatus.COMPLETED) -> None:
        with self._lock:
            removed = self._jobs.pop(job_id, None)
            self._job_started.pop(job_id, None)
            if removed is None:
                return
            self._queue = replace(
                self._queue,
                active_executions=len(self._jobs),
                completed_jobs=self._queue.completed_jobs
                + int(outcome in {ExecutionStatus.COMPLETED, ExecutionStatus.PARTIAL}),
                failed_jobs=self._queue.failed_jobs + int(outcome is ExecutionStatus.FAILED),
                cancelled_jobs=self._queue.cancelled_jobs
                + int(outcome is ExecutionStatus.CANCELLED),
            )

    def record_correlation(
        self,
        *,
        facts: int,
        occurrences: int,
        relations: int,
        duration_ms: float,
        index_ms: float,
        rules_ms: float,
        rules: tuple[CorrelationRuleMetric, ...],
    ) -> None:
        with self._lock:
            ordered_rules = tuple(sorted(rules, key=lambda item: (-item.duration_ms, item.rule_id)))
            self._correlation = CorrelationStats(
                facts,
                occurrences,
                relations,
                len(ordered_rules),
                sum(item.findings > 0 for item in ordered_rules),
                sum(item.failed for item in ordered_rules),
                duration_ms,
                index_ms,
                rules_ms,
                ordered_rules,
            )
            self._mark_milestone("correlation_completed", self._elapsed_ms())

    def mark_correlation_started(self) -> None:
        """Mark the known canonical Case-level correlation boundary once."""
        with self._lock:
            if self._case is not None and self._case.state is ExecutionStatus.RUNNING:
                self._mark_milestone("correlation_started", self._elapsed_ms())

    def _elapsed_ms(self) -> float | None:
        return (
            max(0.0, (perf_counter() - self._case_started) * 1000)
            if self._case_started is not None
            else None
        )

    def _mark_milestone(self, name: str, elapsed_ms: float | None) -> None:
        if (
            self._case is None
            or elapsed_ms is None
            or any(item.name == name for item in self._case.milestones)
        ):
            return
        self._case = replace(
            self._case,
            milestones=(*self._case.milestones, PerformanceMilestone(name, max(0.0, elapsed_ms))),
        )

    def record_error(
        self,
        *,
        component_id: str,
        operation: str | None,
        error_code: str,
        error: BaseException | str,
        file_path: str | None = None,
        case_ref: str | None = None,
    ) -> None:
        error_class = (
            safe_identifier(type(error).__name__)
            if isinstance(error, BaseException)
            else "OperationalError"
        )
        code = safe_identifier(error_code)
        event = OperationalError(
            datetime.now(timezone.utc),
            safe_identifier(component_id),
            safe_identifier(operation) if operation else None,
            code,
            error_class,
            f"{error_class}: {code}. Mensagem original omitida para proteção de dados.",
            safe_ref("file", file_path) if file_path else None,
            safe_identifier(case_ref) if case_ref else None,
        )
        with self._lock:
            self._errors.append(event)

    def set_components(self, components: tuple[ComponentHealth, ...]) -> None:
        with self._lock:
            self._components = tuple(
                replace(
                    item,
                    component_id=safe_identifier(item.component_id),
                    display_name=sanitize_message(item.display_name),
                    message=None,
                    version=sanitize_message(item.version) if item.version else None,
                )
                for item in components
            )

    def snapshot(self) -> ObservabilitySnapshot:
        with self._lock:
            components = self._components
            metrics = tuple(self._metrics)
            artifacts = self._aggregate_artifacts(metrics)
            cache_engine = self._engine_totals.get("analysis_cache")
            cache = (
                ()
                if self._case is None
                else (
                    CacheStats(
                        hits=cache_engine.cache_hits if cache_engine else self._case.cache_hits,
                        misses=cache_engine.cache_misses if cache_engine else self._case.cache_misses,
                        entries=self._cache_entries,
                    ),
                )
            )
            observed_engines = len(
                set(self._engine_totals)
                - {"analysis_pipeline", "analysis_cache", "legacy_correlation"}
            )
            io = (
                None
                if self._case is None
                else IoStats(
                    self._case.total_size_bytes,
                    self._measured_reads,
                    instrumented_engines=len(self._read_engines),
                    observed_engines=observed_engines,
                    state=(
                        MeasurementState.PARTIAL
                        if self._measured_reads is not None
                        else MeasurementState.UNAVAILABLE
                    ),
                )
            )
            case = self._case
            if case and case.state is ExecutionStatus.RUNNING:
                case = replace(
                    case, elapsed_wall_ms=self._elapsed_ms(), running=self._queue.active_executions
                )
            jobs = tuple(
                replace(
                    job,
                    elapsed_ms=max(0.0, (perf_counter() - self._job_started[job.job_id]) * 1000),
                )
                for job in self._jobs.values()
            )
            return ObservabilitySnapshot(
                datetime.now(timezone.utc),
                aggregate_system_health(components),
                components,
                self._aggregate_metrics(),
                tuple(self._errors),
                jobs,
                case,
                self._environment,
                metrics,
                artifacts,
                self._queue,
                cache,
                self._correlation,
                io,
                self._dropped_samples,
                tuple(item for engine in sorted(self._slowest) for item in self._slowest[engine]),
                MeasurementState.PARTIAL if case else MeasurementState.UNAVAILABLE,
            )

    def _aggregate_metrics(self) -> tuple[EngineMetric, ...]:
        return tuple(self._engine_totals[key] for key in sorted(self._engine_totals))

    @staticmethod
    def _aggregate_artifacts(metrics: tuple[ExecutionMetric, ...]) -> tuple[ArtifactMetric, ...]:
        grouped: dict[str, list[ExecutionMetric]] = {}
        for item in metrics:
            if item.file_ref and item.duration_ms is not None:
                grouped.setdefault(item.file_ref, []).append(item)
        result = []
        for artifact_ref, items in grouped.items():
            pipeline = next(
                (item for item in reversed(items) if item.engine_id == "analysis_pipeline"), None
            )
            stages = [item for item in items if item.engine_id != "analysis_pipeline"]
            ordered = sorted(
                stages,
                key=lambda item: (-(item.duration_ms or 0), item.engine_id, item.execution_id),
            )
            failures = any(item.status is ExecutionStatus.FAILED for item in items)
            cancelled = any(item.status is ExecutionStatus.CANCELLED for item in items)
            unavailable = all(item.status is ExecutionStatus.UNAVAILABLE for item in items)
            state = (
                ExecutionStatus.FAILED
                if failures
                else ExecutionStatus.CANCELLED
                if cancelled
                else ExecutionStatus.UNAVAILABLE
                if unavailable
                else ExecutionStatus.PARTIAL
                if any(
                    item.status in {ExecutionStatus.PARTIAL, ExecutionStatus.UNAVAILABLE}
                    for item in items
                )
                else ExecutionStatus.COMPLETED
            )
            size = next(
                (
                    int(item.metadata["size_bytes"])
                    for item in items
                    if isinstance(item.metadata.get("size_bytes"), int)
                ),
                None,
            )
            total = pipeline.duration_ms if pipeline else None
            result.append(
                ArtifactMetric(
                    artifact_ref,
                    total,
                    (ordered[0].operation or ordered[0].engine_id) if ordered else None,
                    ordered[0].duration_ms if ordered else None,
                    size,
                    len({item.engine_id for item in stages} - {"analysis_cache"}),
                    pipeline.status if pipeline else state,
                    tuple(ordered),
                    MeasurementState.AVAILABLE if pipeline else MeasurementState.PARTIAL,
                    False,
                    sum(item.duration_ms or 0 for item in stages),
                )
            )
        return tuple(
            sorted(
                result,
                key=lambda item: (
                    -(
                        item.total_duration_ms
                        if item.total_duration_ms is not None
                        else item.stage_wall_ms
                    ),
                    item.artifact_ref,
                ),
            )
        )


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

    def package_version(name: str) -> str | None:
        try:
            return package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            return None

    try:
        from PySide6.QtCore import qVersion

        qt_version = qVersion()
    except ImportError:
        qt_version = None
    return EnvironmentSnapshot(
        version,
        platform.system(),
        platform.machine(),
        platform.processor() or "Não informado",
        ram,
        disk,
        platform.python_version(),
        core_version,
        logical_cpu_count=os.cpu_count(),
        pyside_version=package_version("PySide6"),
        qt_version=qt_version,
        pyhanko_version=package_version("pyHanko"),
    )

"""Operation-boundary measurements feeding the existing collector on the worker thread.

Bindings never retain evidence, arguments, return values or paths. CPU is not inferred.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Callable, Iterator, ParamSpec, TypeVar
from uuid import uuid4

from app.observability.models import ExecutionMetric, ExecutionStatus
from app.observability.service import ObservabilityService

P = ParamSpec("P")
T = TypeVar("T")
LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProfilingBinding:
    collector: ObservabilityService
    case_ref: str | None
    artifact_ref: str | None
    size_bytes: int | None = None


@dataclass(slots=True)
class _ReadCounter:
    measured: int | None = None


_binding: ContextVar[ProfilingBinding | None] = ContextVar("fh_profiling", default=None)
_reads: ContextVar[_ReadCounter | None] = ContextVar("fh_stage_reads", default=None)


@contextmanager
def profiling_scope(binding: ProfilingBinding | None) -> Iterator[None]:
    token = _binding.set(binding)
    try:
        yield
    finally:
        _binding.reset(token)


def record_bytes_read(count: int) -> None:
    """Called once per measured read loop, using lengths returned by read()."""
    counter = _reads.get()
    if counter is not None and count >= 0:
        counter.measured = (counter.measured or 0) + count


def _outcome(value: object) -> ExecutionStatus | None:
    raw = getattr(value, "status", getattr(value, "analysis_status", getattr(value, "state", None)))
    raw = str(getattr(raw, "value", raw)).lower()
    if raw == "skipped":
        return None
    if raw in {"failed", "error"}:
        return ExecutionStatus.FAILED
    if raw == "unavailable":
        return ExecutionStatus.UNAVAILABLE
    if raw in {"partial", "limit_exceeded"}:
        return ExecutionStatus.PARTIAL
    steps = getattr(value, "processing_steps", ())
    statuses = {str(getattr(step.status, "value", step.status)).lower() for step in steps}
    if "failed" in statuses:
        return ExecutionStatus.PARTIAL
    if statuses and statuses <= {"unavailable", "skipped"} and "unavailable" in statuses:
        return ExecutionStatus.UNAVAILABLE
    if statuses & {"unavailable", "partial", "limit_exceeded"}:
        return ExecutionStatus.PARTIAL
    return ExecutionStatus.COMPLETED


def profile_call(
    engine_id: str, operation: str, call: Callable[P, T], *args: P.args, **kwargs: P.kwargs
) -> T:
    """Measure monotonic elapsed time without changing return/exception contracts."""
    binding = _binding.get()
    if binding is None:
        return call(*args, **kwargs)
    counter = _ReadCounter()
    token = _reads.set(counter)
    started_at = datetime.now(timezone.utc)
    started = perf_counter()
    status: ExecutionStatus | None = ExecutionStatus.FAILED
    try:
        result = call(*args, **kwargs)
        try:
            status = _outcome(result)
        except Exception as error:
            LOGGER.warning("Profiling outcome unavailable (%s)", type(error).__name__)
            status = ExecutionStatus.PARTIAL
        return result
    except BaseException as error:
        if type(error).__name__ in {"AnalysisCancelledError", "CancelledError"}:
            status = ExecutionStatus.CANCELLED
        raise
    finally:
        elapsed_ms = max(0.0, (perf_counter() - started) * 1000)
        _reads.reset(token)
        if status is not None:
            try:
                binding.collector.record_metric(
                    ExecutionMetric(
                        str(uuid4()),
                        engine_id,
                        started_at,
                        datetime.now(timezone.utc),
                        duration_ms=elapsed_ms,
                        status=status,
                        case_ref=binding.case_ref,
                        file_ref=binding.artifact_ref,
                        operation=operation,
                        bytes_read=counter.measured,
                        metadata={"size_bytes": binding.size_bytes},
                    )
                )
            except Exception as error:
                LOGGER.warning("Profiling unavailable (%s)", type(error).__name__)

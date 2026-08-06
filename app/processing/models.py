from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar


class ProcessingStatus(str, Enum):
    SUCCESS = "success"
    NO_FINDINGS = "no_findings"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    CANCELLED = "cancelled"
    LIMIT_EXCEEDED = "limit_exceeded"


class ProcessingImpact(str, Enum):
    NONE = "none"
    COMPONENT_ONLY = "component_only"
    ANALYSIS_PARTIAL = "analysis_partial"
    ANALYSIS_BLOCKED = "analysis_blocked"


class ProcessingLimitExceededError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ProcessingIssue:
    code: str
    status: ProcessingStatus
    technical_message: str
    user_message: str
    component: str
    occurred_at_utc: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, Any] = field(default_factory=dict)
    impact: ProcessingImpact = ProcessingImpact.COMPONENT_ONLY
    original_exception: BaseException | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        if self.occurred_at_utc.tzinfo is None:
            raise ValueError("occurred_at_utc deve conter timezone.")


T = TypeVar("T")


@dataclass(slots=True)
class StepResult(Generic[T]):
    code: str
    component: str
    status: ProcessingStatus
    technical_message: str
    user_message: str
    value: T | None = None
    issues: list[ProcessingIssue] = field(default_factory=list)
    started_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at_utc: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    safe_details: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> int:
        return max(
            0,
            int((self.finished_at_utc - self.started_at_utc).total_seconds() * 1000),
        )

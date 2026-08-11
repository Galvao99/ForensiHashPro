from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.enum.severity import Severity


@dataclass(frozen=True, slots=True)
class TimelineEvent:
    """Fato temporal ou estrutural com proveniencia verificavel.

    ``date``, ``source`` e as propriedades de apresentacao preservam a API
    consumida pela Timeline desktop legada.
    """

    event_id: str
    event_type: str
    category: str
    title: str
    description: str
    timestamp: str | None
    raw_timestamp: str | None
    timezone: str | None
    timezone_status: str
    precision: str | None
    source_type: str
    source_engine: str
    evidence_ref: str
    filename: str
    temporal_status: str
    page: int | None = None
    offset: int | None = None
    field_path: str | None = None
    context: str | None = None
    revision: int | None = None
    structural_sequence: int | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float | None = None
    limitations: tuple[str, ...] = ()
    severity: Severity = Severity.INFO
    color: str = "#60A5FA"
    needs_confirmation: bool = False
    confirmed: bool = True

    @property
    def date(self) -> datetime | None:
        if self.timestamp is None:
            return None
        try:
            return datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except ValueError:
            return None

    @property
    def source(self) -> str:
        return self.source_type

    def formatted_date(self) -> str:
        value = self.date
        return value.strftime("%d/%m/%Y %H:%M:%S") if value else "Data nao determinada"


@dataclass(frozen=True, slots=True)
class TimelineWarning:
    warning_id: str
    rule_id: str
    severity: str
    title: str
    description: str
    evidence_ref: str
    event_ids: tuple[str, ...]
    limitations: tuple[str, ...] = ()


@dataclass(slots=True)
class TimelineResult:
    evidence_ref: str | None
    events: list[TimelineEvent] = field(default_factory=list)
    warnings: list[TimelineWarning] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)

    @property
    def temporal_events(self) -> list[TimelineEvent]:
        return [item for item in self.events if item.temporal_status != "structural_only"]

    @property
    def structural_events(self) -> list[TimelineEvent]:
        return [item for item in self.events if item.temporal_status == "structural_only"]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "events": len(self.events),
            "temporal_events": len(self.temporal_events),
            "structural_events": len(self.structural_events),
            "warnings": len(self.warnings),
        }

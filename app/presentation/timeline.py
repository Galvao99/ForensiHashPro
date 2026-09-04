from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal, Sequence

from app.models.timeline_event import TimelineEvent


TemporalDomain = Literal["instant", "civil"]


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    event: TimelineEvent
    domain: TemporalDomain
    comparable: datetime

    @property
    def event_id(self) -> str:
        return self.event.event_id


@dataclass(frozen=True, slots=True)
class TimelineInterval:
    interval_id: str
    label: str
    start: TimelinePoint
    end: TimelinePoint
    source_type: str
    evidence_ref: str


@dataclass(frozen=True, slots=True)
class TimelinePresentation:
    """Read-only views over one canonical collection of TimelineEvent objects."""

    canonical_events: tuple[TimelineEvent, ...]
    primary_points: tuple[TimelinePoint, ...]
    other_references: tuple[TimelineEvent, ...]
    intervals: tuple[TimelineInterval, ...]

    @classmethod
    def from_events(cls, events: Sequence[TimelineEvent]) -> "TimelinePresentation":
        canonical = tuple(events)
        points = tuple(point for event in canonical if (point := _point(event)) is not None)
        intervals = _certificate_intervals(points)
        interval_members = {
            point.event_id for interval in intervals for point in (interval.start, interval.end)
        }
        references = tuple(
            event for event in canonical
            if event.event_type == "text_date" or event.temporal_status == "structural_only"
        )
        primary = tuple(
            point for point in points
            if point.event_id not in interval_members and point.event not in references
        )
        return cls(canonical, primary, references, intervals)


@dataclass(frozen=True, slots=True)
class TemporalScale:
    domain: TemporalDomain
    start: datetime
    end: datetime

    @classmethod
    def for_points(cls, points: Sequence[TimelinePoint]) -> "TemporalScale | None":
        if not points:
            return None
        domain = points[0].domain
        comparable = [point.comparable for point in points if point.domain == domain]
        if not comparable:
            return None
        return cls(domain, min(comparable), max(comparable))

    def position(self, point: TimelinePoint) -> float | None:
        if point.domain != self.domain:
            return None
        span = (self.end - self.start).total_seconds()
        if span == 0:
            return 0.5
        return max(0.0, min(1.0, (point.comparable - self.start).total_seconds() / span))


def interval_relation(point: TimelinePoint, interval: TimelineInterval) -> str | None:
    """Return only a factual temporal relation for values in the same domain."""
    if point.domain != interval.start.domain or point.domain != interval.end.domain:
        return None
    if point.comparable < interval.start.comparable:
        return "before"
    if point.comparable > interval.end.comparable:
        return "after"
    return "inside"


def _point(event: TimelineEvent) -> TimelinePoint | None:
    value = event.date
    if value is None:
        return None
    aware = value.utcoffset() is not None
    comparable = value.astimezone(timezone.utc).replace(tzinfo=None) if aware else value
    return TimelinePoint(event, "instant" if aware else "civil", comparable)


def _certificate_intervals(points: Sequence[TimelinePoint]) -> tuple[TimelineInterval, ...]:
    starts = [point for point in points if point.event.event_type == "certificate_validity" and point.event.field_path == "valid_from"]
    ends = [point for point in points if point.event.event_type == "certificate_validity" and point.event.field_path == "valid_until"]
    intervals: list[TimelineInterval] = []
    for start in starts:
        end = next((candidate for candidate in ends if candidate.event.evidence_ref == start.event.evidence_ref and candidate.domain == start.domain), None)
        if end is None or end.comparable < start.comparable:
            continue
        intervals.append(TimelineInterval(
            interval_id=f"certificate:{start.event.evidence_ref}:{start.event_id}:{end.event_id}",
            label="Validade do certificado", start=start, end=end,
            source_type=start.event.source_type, evidence_ref=start.event.evidence_ref,
        ))
    return tuple(intervals)

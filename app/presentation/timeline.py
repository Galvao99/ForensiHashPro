from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, Sequence, TYPE_CHECKING

from app.correlation.v2.models import EntityType
from app.correlation.v2.normalization import CorrelationNormalizer
from app.models.timeline_event import TimelineEvent
from app.services.temporal_parser import TemporalParser

if TYPE_CHECKING:
    from app.correlation.v2.pipeline import CanonicalCasePipelineResult


TemporalDomain = Literal["instant", "civil"]
_CORRELATION_NORMALIZER = CorrelationNormalizer()


@dataclass(frozen=True, slots=True)
class TimelineCategory:
    key: str
    label: str
    marker: str


TIMELINE_CATEGORIES = {
    "document": TimelineCategory("document", "DOCUMENTAL", "◆"),
    "signature": TimelineCategory("signature", "ASSINATURA", "■"),
    "metadata": TimelineCategory("metadata", "METADADOS", "●"),
    "filesystem": TimelineCategory("filesystem", "FILESYSTEM", "○"),
    "structural": TimelineCategory("structural", "ESTRUTURAL", "▲"),
    "fh": TimelineCategory("fh", "PROCESSAMENTO FH", "◇"),
    "certificate": TimelineCategory("certificate", "CERTIFICADO", "▰"),
    "reference": TimelineCategory("reference", "REFERÊNCIA TEXTUAL", "◌"),
    "other": TimelineCategory("other", "OUTRA FONTE", "·"),
}


@dataclass(frozen=True, slots=True)
class TimelineVerification:
    finding_id: str
    rule_id: str
    label: str
    statement: str
    state: str
    relation: str | None = None


@dataclass(frozen=True, slots=True)
class TimelinePoint:
    event: TimelineEvent
    domain: TemporalDomain
    comparable: datetime
    position_value: datetime

    @property
    def event_id(self) -> str:
        return self.event.event_id


@dataclass(frozen=True, slots=True)
class TimelineDisplayEvent:
    event: TimelineEvent
    category: TimelineCategory
    title: str
    semantic_role: str | None
    verifications: tuple[TimelineVerification, ...] = ()

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
    verifications: tuple[TimelineVerification, ...] = ()


@dataclass(frozen=True, slots=True)
class TimelinePresentation:
    """Read-only views over one canonical collection of TimelineEvent objects."""

    canonical_events: tuple[TimelineEvent, ...]
    primary_points: tuple[TimelinePoint, ...]
    other_references: tuple[TimelineEvent, ...]
    intervals: tuple[TimelineInterval, ...]
    display_events: tuple[TimelineDisplayEvent, ...] = ()
    related_verifications: tuple[TimelineVerification, ...] = ()
    artifact_id: str | None = None

    @classmethod
    def from_events(
        cls,
        events: Sequence[TimelineEvent],
        *,
        canonical_result: CanonicalCasePipelineResult | None = None,
        artifact_id: str | None = None,
    ) -> "TimelinePresentation":
        canonical = tuple(events)
        points = tuple(
            point for event in canonical if (point := _point(event)) is not None
        )
        base_intervals = _certificate_intervals(points)
        interval_members = {
            point.event_id
            for interval in base_intervals
            for point in (interval.start, interval.end)
        }
        references = tuple(
            event for event in canonical
            if event.event_type == "text_date"
            or event.temporal_status == "structural_only"
        )
        primary = tuple(
            point for point in points
            if point.event_id not in interval_members and point.event not in references
        )
        related_by_event = _related_verifications(
            canonical, canonical_result, artifact_id,
        )
        displays = tuple(
            TimelineDisplayEvent(
                event=event,
                category=category_for_event(event),
                title=presentation_title(event),
                semantic_role=semantic_role_for_event(event),
                verifications=related_by_event.get(event.event_id, ()),
            )
            for event in canonical
        )
        display_by_id = {item.event_id: item for item in displays}
        intervals = tuple(
            TimelineInterval(
                interval.interval_id,
                interval.label,
                interval.start,
                interval.end,
                interval.source_type,
                interval.evidence_ref,
                _unique_verifications(
                    display_by_id[interval.start.event_id].verifications
                    + display_by_id[interval.end.event_id].verifications
                ),
            )
            for interval in base_intervals
        )
        related = _unique_verifications(tuple(
            verification
            for display in displays
            for verification in display.verifications
        ))
        return cls(
            canonical, primary, references, intervals, displays, related, artifact_id,
        )

    def display_event(self, event_id: str) -> TimelineDisplayEvent | None:
        return next(
            (item for item in self.display_events if item.event_id == event_id),
            None,
        )


@dataclass(frozen=True, slots=True)
class TemporalTick:
    position: float
    label: str
    value: datetime


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
        comparable = [
            point.position_value for point in points if point.domain == domain
        ]
        if not comparable:
            return None
        return cls(domain, min(comparable), max(comparable))

    def position(self, point: TimelinePoint) -> float | None:
        if point.domain != self.domain:
            return None
        span = (self.end - self.start).total_seconds()
        if span == 0:
            return 0.5
        return max(
            0.0,
            min(
                1.0,
                (point.position_value - self.start).total_seconds() / span,
            ),
        )

    def ticks(self, maximum: int = 5) -> tuple[TemporalTick, ...]:
        maximum = max(2, min(7, maximum))
        span = self.end - self.start
        seconds = span.total_seconds()
        if seconds <= 0:
            return (TemporalTick(0.5, _tick_label(self.start, 0.0), self.start),)
        ticks: list[TemporalTick] = []
        seen: set[str] = set()
        for index in range(maximum):
            position = index / (maximum - 1)
            value = self.start + timedelta(seconds=seconds * position)
            label = _tick_label(value, seconds)
            if label in seen:
                continue
            seen.add(label)
            ticks.append(TemporalTick(position, label, value))
        return tuple(ticks)


def interval_relation(point: TimelinePoint, interval: TimelineInterval) -> str | None:
    """Return only a factual temporal relation for values in the same domain."""
    if point.domain != interval.start.domain or point.domain != interval.end.domain:
        return None
    if point.comparable < interval.start.comparable:
        return "before"
    if point.comparable > interval.end.comparable:
        return "after"
    return "inside"


def category_for_event(event: TimelineEvent) -> TimelineCategory:
    """Map canonical event properties to presentation-only visual categories."""
    if event.event_type == "contract_date":
        return TIMELINE_CATEGORIES["document"]
    if event.event_type == "text_date":
        return TIMELINE_CATEGORIES["reference"]
    if event.event_type == "certificate_validity":
        return TIMELINE_CATEGORIES["certificate"]
    if event.category == "signature" or event.source_type in {
        "digital_signature", "trusted_timestamp",
    }:
        return TIMELINE_CATEGORIES["signature"]
    if event.category == "metadata" and event.source_type != "filesystem_metadata":
        return TIMELINE_CATEGORIES["metadata"]
    if event.category == "filesystem" or event.source_type in {
        "filesystem", "filesystem_metadata",
    }:
        return TIMELINE_CATEGORIES["filesystem"]
    if event.temporal_status == "structural_only" or event.category == "pdf_structure":
        return TIMELINE_CATEGORIES["structural"]
    if event.category == "operational" or event.source_type == "processing":
        return TIMELINE_CATEGORIES["fh"]
    if event.category == "json":
        return TIMELINE_CATEGORIES["metadata"]
    return TIMELINE_CATEGORIES["other"]


def presentation_title(event: TimelineEvent) -> str:
    if event.event_type == "contract_date":
        return "Data documental observada"
    return event.title


def semantic_role_for_event(event: TimelineEvent) -> str | None:
    if event.event_type == "contract_date":
        return "document_date"
    if event.event_type == "signature":
        return "signer_declared_signing_time"
    if event.event_type == "timestamp_token":
        return "trusted_timestamp_time"
    if event.event_type == "certificate_validity":
        return {
            "valid_from": "certificate_not_before",
            "valid_until": "certificate_not_after",
        }.get(event.field_path)
    if event.category == "metadata" and event.source_type == "metadata":
        return _metadata_role(event.field_path or "")
    return None


def _point(event: TimelineEvent) -> TimelinePoint | None:
    value = event.date
    if value is None:
        return None
    aware = value.utcoffset() is not None
    comparable = (
        value.astimezone(timezone.utc).replace(tzinfo=None) if aware else value
    )
    position_value = comparable
    if event.precision in {"year", "month", "day"}:
        interval = TemporalParser().interval(event.timestamp)
        if interval is not None:
            start = interval.start
            end = interval.end
            if aware:
                start = start.astimezone(timezone.utc).replace(tzinfo=None)
                end = end.astimezone(timezone.utc).replace(tzinfo=None)
            position_value = start + (end - start) / 2
    return TimelinePoint(
        event, "instant" if aware else "civil", comparable, position_value,
    )


def _certificate_intervals(
    points: Sequence[TimelinePoint],
) -> tuple[TimelineInterval, ...]:
    grouped: dict[str, dict[str, list[TimelinePoint]]] = {}
    for point in points:
        if point.event.event_type != "certificate_validity":
            continue
        role = point.event.field_path
        if role not in {"valid_from", "valid_until"}:
            continue
        grouped.setdefault(point.event.evidence_ref, {}).setdefault(role, []).append(point)
    intervals: list[TimelineInterval] = []
    for evidence_ref in sorted(grouped):
        starts = grouped[evidence_ref].get("valid_from", [])
        ends = grouped[evidence_ref].get("valid_until", [])
        # Never bind multiple certificate ranges by discovery order.
        if len(starts) != 1 or len(ends) != 1:
            continue
        start, end = starts[0], ends[0]
        if start.domain != end.domain or end.comparable < start.comparable:
            continue
        intervals.append(TimelineInterval(
            interval_id=(
                f"certificate:{evidence_ref}:{start.event_id}:{end.event_id}"
            ),
            label="VALIDADE DO CERTIFICADO",
            start=start,
            end=end,
            source_type=start.event.source_type,
            evidence_ref=evidence_ref,
        ))
    return tuple(intervals)


def _related_verifications(
    events: tuple[TimelineEvent, ...],
    canonical_result: CanonicalCasePipelineResult | None,
    artifact_id: str | None,
) -> dict[str, tuple[TimelineVerification, ...]]:
    if canonical_result is None or artifact_id is None:
        return {}
    supported_rules = {
        "case.signing_time_certificate_validity",
        "case.document_date_metadata_temporal_relation",
    }
    grouped: dict[str, list[TimelineVerification]] = {}
    for finding in canonical_result.case_result.findings:
        if finding.rule_id not in supported_rules:
            continue
        verification = _verification(finding)
        supports = canonical_result.index.trace_occurrences(
            finding.supporting_occurrence_ids
        )
        for occurrence in supports:
            if occurrence.source_file.stable_id != artifact_id:
                continue
            candidates = [
                event for event in events
                if semantic_role_for_event(event) == occurrence.semantic_role
                and _normalized_timestamp(event) == occurrence.normalized_value
                and _field_compatible(event.field_path, occurrence.provenance.field)
            ]
            if len(candidates) == 1:
                grouped.setdefault(candidates[0].event_id, []).append(verification)
    return {
        event_id: _unique_verifications(tuple(values))
        for event_id, values in grouped.items()
    }


def _verification(finding) -> TimelineVerification:
    if finding.rule_id == "case.signing_time_certificate_validity":
        position = str(finding.metadata.get("position") or "")
        relation = {
            "inside": "SigningTime compreendido no intervalo informado pelo certificado.",
            "before": "SigningTime anterior ao intervalo informado pelo certificado.",
            "after": "SigningTime posterior ao intervalo informado pelo certificado.",
        }.get(position)
        label = "SigningTime × validade do certificado"
    else:
        relation_type = str(finding.metadata.get("relation_type") or "")
        relation = {
            "document_date_before_metadata": (
                "Metadado posterior à data documental observada."
            ),
            "document_date_after_metadata": (
                "Metadado anterior à data documental observada."
            ),
            "temporal_overlap": (
                "Metadado e data documental possuem sobreposição temporal."
            ),
        }.get(relation_type)
        label = "Data documental × metadados"
    return TimelineVerification(
        finding.finding_id,
        finding.rule_id,
        label,
        finding.statement,
        finding.epistemic_state.value,
        relation,
    )


def _unique_verifications(
    values: tuple[TimelineVerification, ...],
) -> tuple[TimelineVerification, ...]:
    return tuple(
        sorted(
            {item.finding_id: item for item in values}.values(),
            key=lambda item: item.finding_id,
        )
    )


def _field_compatible(event_field: str | None, occurrence_field: str | None) -> bool:
    if event_field and occurrence_field:
        return event_field == occurrence_field
    return True


def _normalized_timestamp(event: TimelineEvent) -> str | None:
    if not event.timestamp:
        return None
    normalized = _CORRELATION_NORMALIZER.normalize(
        EntityType.TIMESTAMP, event.timestamp,
    )
    return normalized.value if normalized is not None else None


def _metadata_role(field: str) -> str | None:
    group, separator, leaf = str(field).partition(":")
    if not separator:
        group, leaf = "", group
    group, leaf = group.casefold(), leaf.casefold()
    if group == "pdf":
        return {
            "creationdate": "pdf_creation_date",
            "createdate": "pdf_creation_date",
            "modifydate": "pdf_modify_date",
            "moddate": "pdf_modify_date",
        }.get(leaf)
    if group.startswith("xmp"):
        return {
            "createdate": "xmp_create_date",
            "modifydate": "xmp_modify_date",
            "metadatadate": "xmp_metadata_date",
        }.get(leaf)
    if not group:
        return {
            "creationdate": "metadata_creation_date",
            "createdate": "metadata_creation_date",
            "modifydate": "metadata_modify_date",
            "moddate": "metadata_modify_date",
            "metadatadate": "metadata_date",
        }.get(leaf)
    return None


def _tick_label(value: datetime, span_seconds: float) -> str:
    if span_seconds >= 365 * 24 * 3600 * 2:
        return value.strftime("%Y")
    if span_seconds >= 90 * 24 * 3600:
        months = (
            "jan", "fev", "mar", "abr", "mai", "jun",
            "jul", "ago", "set", "out", "nov", "dez",
        )
        return f"{months[value.month - 1]}/{value.year}"
    if span_seconds >= 2 * 24 * 3600:
        return value.strftime("%d/%m/%Y")
    if span_seconds >= 2 * 3600:
        return value.strftime("%d/%m %H:%M")
    return value.strftime("%H:%M:%S")

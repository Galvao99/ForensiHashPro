from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.correlation.v2 import (
    AnalysisResultCorrelationProvider, CorrelationLimits, EntityType,
    EvidenceGraphCorrelationEngine, JsonCorrelationProvider, JsonProviderLimits,
    OcrCorrelationProvider, RelationType, TextCorrelationProvider,
    TimelineCorrelationProvider, source_file_identity,
)
from app.entities.models import EntitySource, EntitySourceType
from app.entities.models import EntityType as ResolvedEntityType
from app.entities.models import NormalizedEntity
from app.models.json_analysis_result import JsonAnalysisResult, JsonField
from app.models.timeline_event import TimelineEvent
from app.processing import ProcessingStatus, StepResult
from app.services.text_extraction_service import TextExtractionResult, TextSegment


def source_file(name: str = "evidence.pdf"):
    return source_file_identity(display_name=name, path=f"/case/{name}", sha256="a" * 64)


def resolved(
    kind: ResolvedEntityType, normalized: str, raw: str,
    sources: tuple[EntitySource, ...],
) -> NormalizedEntity:
    return NormalizedEntity(kind, normalized, 0.9, (raw,), sources)


def entity_source(
    source_type: EntitySourceType, *, page: int | None = None,
    start: int | None = None, end: int | None = None, path: str | None = None,
    before: str = "", after: str = "",
) -> EntitySource:
    return EntitySource(
        source_type=source_type, source_file="/case/evidence.pdf", page=page,
        start=start, end=end, field_path=path, context_before=before,
        context_after=after, extractor="text_extraction_service",
    )


def result(
    tmp_path: Path, *, entities=(), segments=(), json_analysis=None,
    timeline_events=(), metadata=None, name="evidence.pdf",
):
    steps = []
    if segments:
        text_result = TextExtractionResult(
            text="\n".join(item.text for item in segments), source="ocr",
            segments=list(segments),
        )
        steps.append(StepResult(
            code="text_extraction", component="text_extraction",
            status=ProcessingStatus.SUCCESS, technical_message="ok",
            user_message="ok", value=text_result,
        ))
    return SimpleNamespace(
        file_info=SimpleNamespace(name=name, path=tmp_path / name),
        hashes=SimpleNamespace(sha256="a" * 64, md5="b" * 32),
        metadata=SimpleNamespace(raw=metadata or {}),
        resolved_entities=list(entities), processing_steps=steps,
        extracted_text="\n".join(item.text for item in segments),
        json_analysis=json_analysis, timeline_events=list(timeline_events),
        evidence_source=None,
    )


def temporal_event(
    *, timestamp="2024-09-13T15:18:48-03:00", raw=None,
    source_engine="metadata_engine", source_type="metadata",
    field="EXIF:ModifyDate", event_type="modification", page=None,
):
    return TimelineEvent(
        event_id=f"event-{source_engine}-{field}", event_type=event_type,
        category="metadata", title="ModifyDate", description="Timestamp técnico.",
        timestamp=timestamp, raw_timestamp=raw or timestamp, timezone="-03:00",
        timezone_status="explicit", precision="second", source_type=source_type,
        source_engine=source_engine, evidence_ref="evidence", filename="evidence.pdf",
        temporal_status="temporal", page=page, field_path=field,
    )


@pytest.mark.parametrize(("kind", "normalized", "raw"), [
    (ResolvedEntityType.CPF, "12345678909", "123.456.789-09"),
    (ResolvedEntityType.IP, "177.10.20.30", "177.10.20.30"),
    (ResolvedEntityType.EMAIL, "perito@example.org", "perito@example.org"),
    (ResolvedEntityType.PHONE, "+5521986967225", "+55 21 98696-7225"),
])
def test_text_provider_uses_resolved_entities_and_real_page(
    tmp_path: Path, kind, normalized, raw,
) -> None:
    text = f"Campo: {raw}."
    start = text.index(raw)
    item = resolved(kind, normalized, raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=3, start=start, end=start + len(raw), before="Campo: ", after="."),
    ))
    analysis = result(tmp_path, entities=[item], segments=[TextSegment(text, "native_text", 3)])
    candidates = list(TextCorrelationProvider().provide(analysis, source_file()))
    assert len(candidates) == 1
    assert candidates[0].raw_value == raw
    assert candidates[0].provenance.engine == "text_extraction"
    assert candidates[0].provenance.page == 3
    assert candidates[0].context == text


def test_text_provider_preserves_two_locations_on_same_and_different_pages(tmp_path: Path) -> None:
    raw = "177.10.20.30"
    first_page = f"IP: {raw}; outro IP: {raw}"
    first = first_page.index(raw)
    second = first_page.index(raw, first + 1)
    item = resolved(ResolvedEntityType.IP, raw, raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=1, start=first, end=first + len(raw)),
        entity_source(EntitySourceType.NATIVE_TEXT, page=1, start=second, end=second + len(raw)),
        entity_source(EntitySourceType.NATIVE_TEXT, page=2, start=4, end=4 + len(raw)),
    ))
    analysis = result(tmp_path, entities=[item], segments=[
        TextSegment(first_page, "native_text", 1),
        TextSegment(f"IP: {raw}", "native_text", 2),
    ])
    report = EvidenceGraphCorrelationEngine().correlate(
        TextCorrelationProvider().provide(analysis, source_file())
    )
    occurrence = report.entities[0]
    assert occurrence.occurrence_count == 3
    assert [item.provenance.page for item in occurrence.occurrences] == [1, 1, 2]


def test_text_context_is_limited_by_core_and_url_is_not_invented(tmp_path: Path) -> None:
    raw = "perito@example.org"
    item = resolved(ResolvedEntityType.EMAIL, raw, raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=1, start=300, end=300 + len(raw), before="x" * 300, after="y" * 300),
    ))
    analysis = result(tmp_path, entities=[item], segments=[TextSegment("x" * 300 + raw + "y" * 300, "native_text", 1)])
    report = EvidenceGraphCorrelationEngine(limits=CorrelationLimits(100, 100, 40)).correlate(
        TextCorrelationProvider().provide(analysis, source_file())
    )
    assert len(report.entities[0].occurrences[0].context or "") == 40
    assert all(entity.entity_type is not EntityType.URL for entity in report.entities)


def test_ocr_provider_keeps_page_and_unavailable_bbox_is_none(tmp_path: Path) -> None:
    raw = "123.456.789-09"
    item = resolved(ResolvedEntityType.CPF, "12345678909", raw, (
        entity_source(EntitySourceType.OCR, page=2, start=5, end=19),
    ))
    analysis = result(tmp_path, entities=[item], segments=[TextSegment("CPF: " + raw, "ocr", 2)])
    candidate = next(iter(OcrCorrelationProvider().provide(analysis, source_file())))
    assert candidate.provenance.engine == "ocr"
    assert candidate.provenance.page == 2
    assert candidate.provenance.bbox is None and candidate.provenance.block is None


def test_native_and_ocr_are_two_sources_not_two_files(tmp_path: Path) -> None:
    raw = "177.10.20.30"
    item = resolved(ResolvedEntityType.IP, raw, raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=1, start=4, end=16),
        entity_source(EntitySourceType.OCR, page=1, start=4, end=16),
    ))
    analysis = result(tmp_path, entities=[item], segments=[
        TextSegment("IP: " + raw, "native_text", 1), TextSegment("IP: " + raw, "ocr", 1),
    ])
    provider = AnalysisResultCorrelationProvider(providers=[TextCorrelationProvider(), OcrCorrelationProvider()])
    report = EvidenceGraphCorrelationEngine().correlate(provider.provide_many([analysis]))
    entity = report.entities[0]
    assert (entity.occurrence_count, entity.unique_source_count, entity.unique_file_count) == (2, 2, 1)
    assert RelationType.SAME_ENTITY_ACROSS_FILES not in {item.relation_type for item in report.relations}


def json_result(*fields: JsonField) -> JsonAnalysisResult:
    value = JsonAnalysisResult(is_valid=True, total_fields=len(fields), displayed_fields=len(fields))
    for field in fields:
        value.add_field(field)
    return value


@pytest.mark.parametrize(("key", "raw", "entity_type"), [
    ("ip", "177.10.20.30", EntityType.IP),
    ("cpf", "123.456.789-09", EntityType.CPF),
    ("cnpj", "04.252.011/0001-10", EntityType.CNPJ),
    ("email", "agent@example.org", EntityType.EMAIL),
    ("phone", "+55 21 98696-7225", EntityType.PHONE),
    ("url", "https://example.org/a", EntityType.URL),
    ("timestamp", "2024-09-13T15:18:48-03:00", EntityType.TIMESTAMP),
    ("sha256", "a" * 64, EntityType.SHA256),
    ("md5", "b" * 32, EntityType.MD5),
    ("filename", "Contract.PDF", EntityType.FILENAME),
    ("document_identifier", "DOC-2024-009", EntityType.DOCUMENT_IDENTIFIER),
])
def test_json_provider_uses_structured_key_and_path(tmp_path: Path, key, raw, entity_type) -> None:
    path = f"events[4].{key}"
    analysis = result(tmp_path, json_analysis=json_result(JsonField(path, key, raw, "string")))
    candidate = next(iter(JsonCorrelationProvider().provide(analysis, source_file())))
    assert candidate.entity_type is entity_type
    assert candidate.provenance.path == path
    assert candidate.provenance.field == key
    assert candidate.provenance.engine == "json_engine"


def test_json_arrays_nested_paths_and_deterministic_order(tmp_path: Path) -> None:
    analysis = result(tmp_path, json_analysis=json_result(
        JsonField("users[1].email", "email", "b@example.org", "string"),
        JsonField("users[0].email", "email", "a@example.org", "string"),
    ))
    provider = JsonCorrelationProvider()
    first = list(provider.provide(analysis, source_file()))
    second = list(provider.provide(analysis, source_file()))
    assert [item.provenance.path for item in first] == ["users[0].email", "users[1].email"]
    assert first == second


def test_json_limits_fields_depth_and_string_size(tmp_path: Path) -> None:
    analysis = result(tmp_path, json_analysis=json_result(
        JsonField("a.email", "email", "first@example.org", "string"),
        JsonField("a.b.c.email", "email", "deep@example.org", "string"),
        JsonField("z.email", "email", "x" * 50, "string"),
        JsonField("zz.email", "email", "ignored@example.org", "string"),
    ))
    provider = JsonCorrelationProvider(JsonProviderLimits(
        max_fields=10, max_nodes=3, max_depth=2, max_string_length=30,
    ))
    candidates = list(provider.provide(analysis, source_file()))
    assert [item.raw_value for item in candidates] == ["first@example.org"]


def test_timeline_preserves_original_source_event_timezone_and_precision(tmp_path: Path) -> None:
    event = temporal_event(page=4)
    analysis = result(tmp_path, timeline_events=[event])
    candidate = next(iter(TimelineCorrelationProvider().provide(analysis, source_file())))
    assert candidate.raw_value == "2024-09-13T15:18:48-03:00"
    assert candidate.provenance.engine == "metadata_engine"
    assert candidate.provenance.source_engine == "metadata"
    assert candidate.provenance.event_type == "modification"
    assert candidate.provenance.page == 4
    assert candidate.provenance.derived_view == "timeline"


def test_timeline_uses_resolved_timestamp_without_losing_non_iso_raw(tmp_path: Path) -> None:
    event = temporal_event(
        timestamp="2024-09-13T15:18:48-03:00",
        raw="2024:09:13 15:18:48-03:00",
    )
    analysis = result(tmp_path, timeline_events=[event])
    report = EvidenceGraphCorrelationEngine().correlate(
        TimelineCorrelationProvider().provide(analysis, source_file())
    )
    occurrence = report.entities[0].occurrences[0]
    assert occurrence.raw_value == "2024:09:13 15:18:48-03:00"
    assert occurrence.normalized_value == "2024-09-13T15:18:48-03:00"
    assert occurrence.provenance.source_timestamp == occurrence.raw_value


def test_timeline_deduplicates_against_primary_metadata(tmp_path: Path) -> None:
    timestamp = "2024-09-13T15:18:48-03:00"
    analysis = result(
        tmp_path, metadata={"EXIF:ModifyDate": timestamp},
        timeline_events=[temporal_event(timestamp=timestamp)],
    )
    report = EvidenceGraphCorrelationEngine().correlate(
        AnalysisResultCorrelationProvider().provide_many([analysis])
    )
    item = next(entity for entity in report.entities if entity.entity_type is EntityType.TIMESTAMP)
    assert item.occurrence_count == 1
    assert item.occurrences[0].provenance.derived_view is None
    assert item.occurrences[0].provenance.engine == "metadata_engine"


def test_timeline_deduplicates_against_primary_json(tmp_path: Path) -> None:
    timestamp = "2024-09-13T15:18:48-03:00"
    field = JsonField("events[0].timestamp", "timestamp", timestamp, "string")
    event = temporal_event(
        timestamp=timestamp, source_engine="json_engine", source_type="json",
        field=field.path, event_type="json_event",
    )
    event = replace(event, attributes={"key": "timestamp"})
    analysis = result(tmp_path, json_analysis=json_result(field), timeline_events=[event])
    report = EvidenceGraphCorrelationEngine().correlate(
        AnalysisResultCorrelationProvider().provide_many([analysis])
    )
    item = next(entity for entity in report.entities if entity.entity_type is EntityType.TIMESTAMP)
    assert item.occurrence_count == 1
    assert item.occurrences[0].provenance.engine == "json_engine"


def test_provider_enable_disable_and_full_report_determinism(tmp_path: Path) -> None:
    raw = "177.10.20.30"
    item = resolved(ResolvedEntityType.IP, raw, raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=1, start=4, end=16),
    ))
    analysis = result(tmp_path, entities=[item], segments=[TextSegment("IP: " + raw, "native_text", 1)])
    disabled = AnalysisResultCorrelationProvider(disabled={"text", "ocr", "json", "timeline", "metadata", "ip", "resolved_entity"})
    assert {candidate.entity_type for candidate in disabled.provide_many([analysis])} == {EntityType.SHA256, EntityType.MD5}
    enabled = AnalysisResultCorrelationProvider(providers=[TextCorrelationProvider()])
    engine = EvidenceGraphCorrelationEngine()
    assert engine.correlate(enabled.provide_many([analysis])).to_dict() == engine.correlate(enabled.provide_many([analysis])).to_dict()


def test_text_and_json_same_cpf_across_files_create_factual_relation(tmp_path: Path) -> None:
    raw = "123.456.789-09"
    item = resolved(ResolvedEntityType.CPF, "12345678909", raw, (
        entity_source(EntitySourceType.NATIVE_TEXT, page=3, start=5, end=19),
    ))
    text_result = result(
        tmp_path, name="contract.pdf", entities=[item],
        segments=[TextSegment("CPF: " + raw, "native_text", 3)],
    )
    json_analysis = result(
        tmp_path, name="logs.json",
        json_analysis=json_result(JsonField("contract.cpf", "cpf", "12345678909", "string")),
    )
    provider = AnalysisResultCorrelationProvider(providers=[TextCorrelationProvider(), JsonCorrelationProvider()])
    report = EvidenceGraphCorrelationEngine().correlate(provider.provide_many([text_result, json_analysis]))
    cpf = next(item for item in report.entities if item.entity_type is EntityType.CPF)
    assert (cpf.occurrence_count, cpf.unique_file_count, cpf.unique_source_count) == (2, 2, 2)
    assert RelationType.SAME_ENTITY_ACROSS_FILES in {item.relation_type for item in report.relations}
    assert report.to_dict()["summary"]["cross_file_entities"] == 1

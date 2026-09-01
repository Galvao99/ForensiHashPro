from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.contracts import AnalysisContract, AnalysisState
from app.investigation.analysis_set import AnalysisSetArtifact, AnalysisSetCorrelator
from app.models import PdfRawAnalysisResult, PdfStartXref
from app.models.json_analysis_result import JsonAnalysisResult, JsonField
from app.services.temporal_parser import TemporalParser
from app.services.timeline_service import TimelineService


def _result(**overrides):
    values = dict(
        metadata=SimpleNamespace(raw={}),
        file_info=SimpleNamespace(
            name="contrato.pdf", created_at=None, modified_at=None, accessed_at=None
        ),
        hashes=SimpleNamespace(sha256="a" * 64), evidence_source=None,
        extracted_text="", processing_steps=[],
        digital_signature=SimpleNamespace(
            signing_time=None, timestamp=None, valid_from=None, valid_until=None
        ),
        json_analysis=None, binary_analysis=None, pdf_structure=None,
        analyzed_at=datetime(2026, 8, 11, 12, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 11, 12, 1, tzinfo=timezone.utc),
    )
    values.update(overrides)
    return SimpleNamespace(**values)


@pytest.mark.parametrize(
    ("raw", "precision", "timezone_status", "normalized"),
    [
        ("2023", "year", "unknown", "2023"),
        ("2023-01", "month", "unknown", "2023-01"),
        ("2023-01-26", "day", "unknown", "2023-01-26"),
        ("2023-01-26 15:51", "minute", "unknown", "2023-01-26T15:51"),
        ("2023-01-26T15:51:40", "second", "unknown", "2023-01-26T15:51:40"),
        ("2023-01-26T15:51:40.847", "millisecond", "unknown", "2023-01-26T15:51:40.847"),
        ("2023-01-26T15:51:40Z", "second", "explicit", "2023-01-26T15:51:40Z"),
        ("D:20230126155140-03'00'", "second", "explicit", "2023-01-26T15:51:40-03:00"),
        ("26/01/2023", "day", "unknown", "2023-01-26"),
    ],
)
def test_temporal_parser_preserves_precision_timezone_and_raw(
    raw, precision, timezone_status, normalized
):
    parsed = TemporalParser().parse(raw)
    assert parsed is not None
    assert parsed.raw == raw
    assert parsed.precision == precision
    assert parsed.timezone_status == timezone_status
    assert parsed.normalized == normalized


@pytest.mark.parametrize("raw", ["", "not-a-date", "2023-02-31", 1690000000])
def test_temporal_parser_rejects_unsupported_values(raw):
    assert TemporalParser().parse(raw) is None


def test_temporal_order_key_compares_aware_values_by_utc_instant():
    parser = TemporalParser()
    earlier = parser.order_key("2023-01-26T15:00:00-03:00")
    later = parser.order_key("2023-01-26T19:00:00Z")
    same_instant = parser.order_key("2023-01-26T18:00:00Z")
    assert earlier is not None and later is not None and same_instant is not None
    assert earlier < later
    assert earlier[:2] == same_instant[:2]


def test_temporal_order_key_keeps_naive_in_separate_domain_without_inventing_zone():
    parser = TemporalParser()
    naive = parser.parse("2023-01-26 15:50:00")
    aware = parser.parse("2023-01-26T15:50:00Z")
    assert naive is not None and aware is not None
    assert naive.raw == "2023-01-26 15:50:00"
    assert naive.timezone_status == "unknown"
    assert naive.utc_normalized is None
    assert parser.order_key(aware)[0] == 0
    assert parser.order_key(naive)[0] == 1


def test_mixed_timezone_timeline_order_is_deterministic_and_preserves_raw():
    result = _result(metadata=SimpleNamespace(raw={
        "PDF:CreationDate": "2023-01-26 15:50:00",
        "PDF:ModifyDate": "2023-01-26T17:00:00-03:00",
        "XMP:MetadataDate": "2023-01-26T19:00:00Z",
    }))
    first = TimelineService().build(result).events
    second = TimelineService().build(result).events
    assert [item.event_id for item in first] == [item.event_id for item in second]
    assert any(item.raw_timestamp == "2023-01-26 15:50:00" for item in first)
    assert TimelineService().build(result).warnings == []


def test_metadata_creation_modification_and_objective_warning():
    result = _result(metadata=SimpleNamespace(raw={
        "PDF:CreationDate": "2024-01-10T10:00:00-03:00",
        "PDF:ModifyDate": "2023-12-01T10:00:00-03:00",
        "XMP:MetadataDate": "2024-01-11",
    }))
    timeline = TimelineService().build(result)
    assert {item.title for item in timeline.events} >= {"CreationDate", "ModifyDate", "MetadataDate"}
    assert len(timeline.warnings) == 1
    assert "é anterior" in timeline.warnings[0].description
    assert all("fraude" not in item.description.lower() for item in timeline.warnings)


def test_normal_metadata_order_has_no_warning():
    result = _result(metadata=SimpleNamespace(raw={
        "PDF:CreationDate": "2023-01-01", "PDF:ModifyDate": "2023-01-02"
    }))
    assert TimelineService().build(result).warnings == []


def test_contract_and_generic_text_dates_keep_context_and_offset():
    result = _result(extracted_text=(
        "Data da contratação: 15/07/2026. Data de emissão: 14/07/2026."
    ))
    timeline = TimelineService().build(result)
    contract = next(item for item in timeline.events if item.event_type == "contract_date")
    generic = next(item for item in timeline.events if item.event_type == "text_date")
    assert contract.raw_timestamp == "15/07/2026"
    assert contract.context and contract.offset is not None
    assert generic.title == "Data identificada no texto"


def test_signature_events_do_not_confuse_certificate_validity():
    result = _result(digital_signature=SimpleNamespace(
        signing_time="2023-01-26T15:51:40Z", timestamp=None,
        valid_from="2022-01-01T00:00:00Z", valid_until="2024-01-01T00:00:00Z",
    ))
    timeline = TimelineService().build(result)
    signing = [item for item in timeline.events if item.event_type == "signature"]
    validity = [item for item in timeline.events if item.event_type == "certificate_validity"]
    assert len(signing) == 1 and len(validity) == 2
    assert all("não representa o momento da assinatura" in item.description for item in validity)


def test_json_timestamp_preserves_field_path_and_invalid_is_ignored():
    analysis = JsonAnalysisResult(is_valid=True)
    analysis.fields = [
        JsonField("events[0].created_at", "created_at", "2023-01-26T15:51:40Z", "string"),
        JsonField("events[0].updated_at", "updated_at", "invalid", "string"),
        JsonField("events[0].timestamp", "timestamp", 1690000000, "number"),
    ]
    events = TimelineService().build(_result(json_analysis=analysis)).events
    json_events = [item for item in events if item.category == "json"]
    assert len(json_events) == 1
    assert json_events[0].field_path == "events[0].created_at"


def test_filesystem_events_are_explicit_and_limited():
    result = _result(file_info=SimpleNamespace(
        name="a.pdf", created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        modified_at=None, accessed_at=None,
    ))
    event = next(item for item in TimelineService().build(result).events if item.category == "filesystem")
    assert event.source_type == "filesystem"
    assert event.limitations


def _raw_pdf(revisions: int, *, stream=False) -> PdfRawAnalysisResult:
    offsets = [100 + index * 100 for index in range(revisions)]
    return PdfRawAnalysisResult(
        xref_offsets=[] if stream else offsets,
        xref_stream_offsets=offsets if stream else [],
        trailer_offsets=[80 + index * 100 for index in range(revisions)],
        startxrefs=[PdfStartXref(90 + index * 100, offset) for index, offset in enumerate(offsets)],
        eof_offsets=[150 + index * 100 for index in range(revisions)],
        prev_offsets=offsets[:-1],
    )


@pytest.mark.parametrize("revisions", [1, 2, 3])
def test_pdf_revision_sequence_without_invented_timestamp(revisions):
    binary = SimpleNamespace(pdf_raw_analysis=_raw_pdf(revisions))
    events = TimelineService().build(_result(binary_analysis=binary)).structural_events
    assert len(events) == revisions
    assert [item.structural_sequence for item in events] == list(range(1, revisions + 1))
    assert all(item.timestamp is None and item.temporal_status == "structural_only" for item in events)
    if revisions > 1:
        assert events[1].title == "Incremental Update #1"


def test_pdf_xref_stream_prev_offset_and_trailer_are_preserved():
    binary = SimpleNamespace(pdf_raw_analysis=_raw_pdf(2, stream=True))
    event = TimelineService().build(_result(binary_analysis=binary)).structural_events[1]
    assert event.offset == 200
    assert event.attributes["xref_type"] == "xref_stream"
    assert event.attributes["prev"] == 100
    assert event.attributes["trailer_offset"] == 180


def test_structural_revision_limitation_is_explicit():
    binary = SimpleNamespace(pdf_raw_analysis=_raw_pdf(2))
    timeline = TimelineService().build(_result(binary_analysis=binary))
    assert any("não associa" in item for item in timeline.limitations)


def test_event_id_is_stable_and_provenance_is_complete():
    result = _result(metadata=SimpleNamespace(raw={"PDF:CreationDate": "2023-01-01"}))
    first = TimelineService().build(result).events
    second = TimelineService().build(result).events
    event = next(item for item in first if item.event_type == "creation")
    assert event.event_id == next(item for item in second if item.event_type == "creation").event_id
    assert event.evidence_ref and event.filename and event.field_path and event.source_engine


def _contract(evidence_id: str, timeline):
    return AnalysisContract(
        schema_version="1.0.0", analysis_id=f"analysis-{evidence_id}", evidence_id=evidence_id,
        state=AnalysisState.COMPLETED, file={"name": f"{evidence_id}.pdf"}, hashes={},
        declared_type="pdf", detected_type="pdf", timeline=timeline,
    )


def test_analysis_set_aggregates_contract_timeline_and_tolerates_failed_member():
    record = {
        "record_type": "event", "event_id": "event-a", "title": "CreationDate",
        "timestamp": "2023-01-01", "temporal_status": "date_only",
        "evidence_ref": "old", "filename": "internal-path.pdf",
    }
    artifacts = [
        AnalysisSetArtifact("job-a", "completed", evidence_ref="a", filename="a.pdf", contract=_contract("a", [record])),
        AnalysisSetArtifact("job-b", "failed", evidence_ref="b", filename="b.pdf", limitation="b.pdf falhou"),
    ]
    result = AnalysisSetCorrelator().correlate("set-1", artifacts)
    assert result.state == "partial"
    assert result.timeline_result["events"][0]["filename"] == "a.pdf"
    assert result.timeline_result["events"][0]["evidence_ref"] == "a"
    assert "b.pdf falhou" in result.timeline_result["limitations"]


def test_analysis_set_with_one_artifact_preserves_individual_contract():
    contract = _contract("a", [])
    artifact = AnalysisSetArtifact("job-a", "completed", evidence_ref="a", filename="a.pdf", contract=contract)
    result = AnalysisSetCorrelator().correlate("set-1", [artifact])
    assert result.state == "completed"
    assert contract.timeline == []


def test_operational_events_are_separate_from_document_history():
    timeline = TimelineService().build(_result())
    assert {item.category for item in timeline.events} == {"operational"}
    assert all("não integra a história documental" in item.description for item in timeline.events)

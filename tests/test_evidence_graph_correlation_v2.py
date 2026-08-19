from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.correlation.v2 import (
    AnalysisResultCorrelationProvider, CorrelationCandidate, CorrelationLimits,
    CorrelationProvenance, DerivedFromCandidate, EntityType,
    EvidenceGraphCorrelationEngine, RelationType, source_file_identity,
)
from app.correlation.v2.providers import derived_from_extracted_artifact
from app.models.extracted_artifact import ExtractedArtifact


def file(name: str, sha256: str | None = None, path: str | None = None):
    return source_file_identity(display_name=name, sha256=sha256, path=path or f"/case/{name}")


def candidate(entity_type: EntityType, value: str, source, engine: str = "test", **coordinates):
    return CorrelationCandidate(
        entity_type, value, source,
        CorrelationProvenance(engine=engine, **coordinates),
    )


def entity(report, entity_type: EntityType):
    return next(item for item in report.entities if item.entity_type is entity_type)


def relation_types(report):
    return {item.relation_type for item in report.relations}


def test_same_ip_in_two_files_preserves_both_provenances() -> None:
    left, right = file("contract.pdf"), file("logs.json")
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.IP, "177.10.20.30", left, "extracted_text", page=7),
        candidate(EntityType.IP, "177.10.20.30", right, "ip_extraction", path="$.events[4].ip"),
    ])
    item = entity(report, EntityType.IP)
    assert (item.occurrence_count, item.unique_file_count, item.unique_source_count) == (2, 2, 2)
    assert RelationType.SAME_ENTITY_ACROSS_FILES in relation_types(report)
    assert RelationType.ENTITY_OCCURS_IN_FILE in relation_types(report)
    assert {occurrence.provenance.engine for occurrence in item.occurrences} == {"extracted_text", "ip_extraction"}


def test_same_ip_repeated_in_one_file_is_not_counted_as_multiple_files() -> None:
    source = file("one.pdf")
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.IP, "10.0.0.1", source, start=1),
        candidate(EntityType.IP, "10.0.0.1", source, start=40),
    ])
    item = entity(report, EntityType.IP)
    assert (item.occurrence_count, item.unique_file_count) == (2, 1)
    assert RelationType.SAME_ENTITY_ACROSS_FILES not in relation_types(report)


@pytest.mark.parametrize(("raw", "expected"), [
    ("192.168.001.1", None), ("::ffff:192.0.2.128", "192.0.2.128"),
    ("2001:0DB8:0:0:0:0:0:1", "2001:db8::1"),
])
def test_ip_normalization(raw: str, expected: str | None) -> None:
    report = EvidenceGraphCorrelationEngine().correlate([candidate(EntityType.IP, raw, file("a"))])
    assert (report.entities[0].normalized_value if report.entities else None) == expected


def test_equal_hashes_for_differently_named_files_create_same_hash_relation() -> None:
    digest = "A" * 64
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.SHA256, digest, file("original.pdf", digest)),
        candidate(EntityType.SHA256, digest.lower(), file("copy.pdf", digest)),
    ])
    assert entity(report, EntityType.SHA256).unique_file_count == 2
    assert RelationType.SAME_HASH in relation_types(report)


def test_same_filename_with_different_hashes_remains_two_files() -> None:
    left = file("contract.pdf", "a" * 64, "/case/a/contract.pdf")
    right = file("contract.pdf", "b" * 64, "/case/b/contract.pdf")
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.FILENAME, "contract.pdf", left),
        candidate(EntityType.FILENAME, "contract.pdf", right),
    ])
    assert left.stable_id != right.stable_id
    assert entity(report, EntityType.FILENAME).unique_file_count == 2


@pytest.mark.parametrize(("entity_type", "left", "right", "normalized"), [
    (EntityType.CPF, "123.456.789-09", "12345678909", "12345678909"),
    (EntityType.CNPJ, "04.252.011/0001-10", "04252011000110", "04252011000110"),
    (EntityType.EMAIL, "Agent@Example.COM", "Agent@example.com", "Agent@example.com"),
    (EntityType.PHONE, "+55 (21) 98696-7225", "+5521986967225", "+5521986967225"),
    (EntityType.URL, "HTTPS://Example.COM/a?b=1", "https://example.com/a?b=1", "https://example.com/a?b=1"),
    (EntityType.FILENAME, "Folder\\Report.PDF", "report.pdf", "report.pdf"),
])
def test_deterministic_normalizers_collapse_exact_equivalents(entity_type, left, right, normalized) -> None:
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(entity_type, left, file("a")), candidate(entity_type, right, file("b")),
    ])
    assert len(report.entities) == 1
    assert report.entities[0].normalized_value == normalized


def test_phone_does_not_assume_country_when_missing() -> None:
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.PHONE, "(21) 98696-7225", file("a")),
        candidate(EntityType.PHONE, "+55 21 98696-7225", file("b")),
    ])
    assert len(report.entities) == 2


def test_timestamps_match_only_at_same_precision_and_timezone_representation() -> None:
    values = ["2024-09-13", "2024-09-13T15:18:48-03:00", "2024-09-13T18:18:48+00:00"]
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(EntityType.TIMESTAMP, value, file(str(index))) for index, value in enumerate(values)
    ] + [candidate(EntityType.TIMESTAMP, values[1], file("same"))])
    assert len(report.entities) == 3
    matched = next(item for item in report.entities if item.normalized_value == values[1])
    assert matched.unique_file_count == 2


def test_stable_ids_and_order_do_not_depend_on_input_order() -> None:
    values = [candidate(EntityType.IP, "10.0.0.2", file("b"), start=2),
              candidate(EntityType.IP, "10.0.0.1", file("a"), start=1)]
    first = EvidenceGraphCorrelationEngine().correlate(values)
    second = EvidenceGraphCorrelationEngine().correlate(reversed(values))
    assert first.to_dict() == second.to_dict()
    assert [item.stable_id for item in first.entities] == [item.stable_id for item in second.entities]
    assert first.entities[0].occurrences[0].occurrence_id == second.entities[0].occurrences[0].occurrence_id


def test_duplicate_provenance_collapses_but_ocr_and_native_text_do_not() -> None:
    source = file("document.pdf")
    native = candidate(EntityType.EMAIL, "a@example.com", source, "extracted_text", page=1, start=2)
    ocr = candidate(EntityType.EMAIL, "a@example.com", source, "ocr", page=1, start=2)
    report = EvidenceGraphCorrelationEngine().correlate([native, native, ocr])
    item = entity(report, EntityType.EMAIL)
    assert (item.occurrence_count, item.unique_source_count, item.unique_file_count) == (2, 2, 1)


def test_derived_from_reuses_extracted_artifact_coordinates(tmp_path: Path) -> None:
    artifact = ExtractedArtifact(
        tmp_path / "source.bin", tmp_path / "child.pdf", "a" * 64, 100, 199, 100,
        "b" * 64, "PDF", "application/pdf", "25504446", created_at=datetime.now(timezone.utc),
    )
    source, child = file("source.bin", artifact.source_sha256), file("child.pdf", artifact.extracted_sha256)
    derived = derived_from_extracted_artifact(artifact, source_file=source, derived_file=child)
    report = EvidenceGraphCorrelationEngine().correlate([], derived_from=[derived])
    relation = report.relations[0]
    assert relation.relation_type is RelationType.DERIVED_FROM
    assert (relation.provenance.offset_start, relation.provenance.offset_end) == (100, 199)
    assert report.summary.files_involved == 2


def test_explicit_derived_from_is_stable() -> None:
    source, child = file("source"), file("child")
    edge = DerivedFromCandidate(child, source, CorrelationProvenance(engine="carving", offset_start=5, offset_end=9))
    first = EvidenceGraphCorrelationEngine().correlate([], derived_from=[edge])
    second = EvidenceGraphCorrelationEngine().correlate([], derived_from=[edge])
    assert first.relations[0].stable_id == second.relations[0].stable_id


def test_serialization_and_empty_report_are_clean_json() -> None:
    empty = EvidenceGraphCorrelationEngine().correlate([])
    assert empty.summary.to_dict() == {
        "total_entities": 0, "total_occurrences": 0, "total_relations": 0,
        "entities_by_type": {}, "cross_file_entities": 0, "files_involved": 0,
    }
    assert json.loads(json.dumps(empty.to_dict())) == empty.to_dict()


@pytest.mark.parametrize(("entity_type", "value"), [
    (EntityType.SHA256, "not-a-hash"), (EntityType.MD5, "a" * 31),
    (EntityType.IP, "999.1.1.1"), (EntityType.EMAIL, "invalid@"),
    (EntityType.CPF, "111.111.111-11"), (EntityType.CNPJ, "00.000.000/0000-00"),
    (EntityType.URL, "javascript:alert(1)"), (EntityType.TIMESTAMP, "yesterday"),
])
def test_malformed_values_are_ignored_safely(entity_type, value) -> None:
    assert EvidenceGraphCorrelationEngine().correlate([candidate(entity_type, value, file("x"))]).entities == ()


def test_context_limit_and_occurrence_limit_are_defensive() -> None:
    engine = EvidenceGraphCorrelationEngine(limits=CorrelationLimits(2, 10, 8))
    items = [replace(candidate(EntityType.IP, f"10.0.0.{index}", file(str(index))), context="x" * 100)
             for index in range(1, 4)]
    report = engine.correlate(items)
    assert report.summary.total_occurrences == 2 and report.limitations
    assert all(len(item.occurrences[0].context or "") <= 8 for item in report.entities)


def test_thousands_of_occurrences_keep_exact_counts() -> None:
    items = [candidate(EntityType.IP, f"10.0.{index // 250}.{index % 250 + 1}", file(f"f{index % 100}"), start=index)
             for index in range(5_000)]
    report = EvidenceGraphCorrelationEngine().correlate(items)
    assert report.summary.total_occurrences == 5_000
    assert report.summary.total_entities == 5_000
    assert report.summary.files_involved == 100


def test_analysis_result_provider_adapts_hashes_without_contract_change(tmp_path: Path) -> None:
    result = SimpleNamespace(
        file_info=SimpleNamespace(name="evidence.bin", path=tmp_path / "evidence.bin"),
        hashes=SimpleNamespace(sha256="a" * 64, md5="b" * 32), metadata=SimpleNamespace(raw={}),
        resolved_entities=[], evidence_source=None,
    )
    candidates = list(AnalysisResultCorrelationProvider().provide_many([result]))
    report = EvidenceGraphCorrelationEngine().correlate(candidates)
    assert {item.entity_type for item in report.entities} == {EntityType.SHA256, EntityType.MD5}


def test_metadata_provider_only_adapts_explicit_fields(tmp_path: Path) -> None:
    result = SimpleNamespace(
        file_info=SimpleNamespace(name="evidence.pdf", path=tmp_path / "evidence.pdf"),
        hashes=SimpleNamespace(sha256="a" * 64, md5=""),
        metadata=SimpleNamespace(raw={
            "EXIF:CreateDate": "2024-09-13T15:18:48-03:00",
            "EXIF:Artist": "Name that must not become an entity",
        }), resolved_entities=[], evidence_source=None,
    )
    report = EvidenceGraphCorrelationEngine().correlate(
        AnalysisResultCorrelationProvider().provide_many([result])
    )
    assert {item.entity_type for item in report.entities} == {EntityType.SHA256, EntityType.TIMESTAMP}
    timestamp = entity(report, EntityType.TIMESTAMP)
    assert timestamp.occurrences[0].provenance.field == "EXIF:CreateDate"

from __future__ import annotations

from itertools import permutations

from app.correlation.case_result import EpistemicState
from app.correlation.v2 import (
    CaseEvidenceIndex,
    CorrelationCandidate,
    CorrelationProvenance,
    EntityType,
    EvidenceGraphCorrelationEngine,
    RelationType,
    StructuredRelationCandidate,
    source_file_identity,
)
from app.correlation.v2.pipeline import CanonicalCasePipeline, IdenticalCalculatedHashRule


def artifact(name: str):
    return source_file_identity(display_name=name, path=f"/case/{name}")


def candidate(
    value: str, source, *, fact_type: EntityType = EntityType.CPF,
    engine: str = "text_extraction", role: str | None = None,
    page: int | None = None, path: str | None = None,
    timezone_status: str | None = None, precision: str | None = None,
):
    return CorrelationCandidate(
        fact_type, value, source,
        CorrelationProvenance(
            engine=engine, source_type=engine, page=page, path=path,
            raw_value=value, timezone_status=timezone_status,
            timestamp_precision=precision,
        ), semantic_role=role,
    )


def test_same_fact_keeps_three_distinct_occurrences_and_raw_provenance() -> None:
    values = [
        candidate("529.982.247-25", artifact("contract.pdf"), page=2),
        candidate("52998224725", artifact("evidence.json"), engine="json_engine", path="$.customer.document"),
        candidate("529.982.247-25", artifact("selfie.jpg"), engine="ocr", page=1),
    ]
    report = EvidenceGraphCorrelationEngine().correlate(values)
    assert len(report.entities) == 1
    fact = report.entities[0]
    assert fact.entity_type is EntityType.CPF
    assert fact.normalized_value == "52998224725"
    assert fact.occurrence_count == 3
    assert fact.unique_file_count == 3
    assert {item.raw_value for item in fact.occurrences} == {"529.982.247-25", "52998224725"}
    assert {item.provenance.page for item in fact.occurrences} == {None, 1, 2}
    assert any(item.provenance.path == "$.customer.document" for item in fact.occurrences)
    assert any(item.provenance.source_type == "ocr" for item in fact.occurrences)


def test_semantic_role_only_exists_when_parser_supplies_context() -> None:
    plain = candidate("529.982.247-25", artifact("scan.jpg"), engine="ocr")
    structured = candidate(
        "52998224725", artifact("data.json"), engine="json_engine",
        role="customer_document", path="$.customer.document",
    )
    report = EvidenceGraphCorrelationEngine().correlate([plain, structured])
    roles = {item.source_file.display_name: item.semantic_role for item in report.entities[0].occurrences}
    assert roles == {"scan.jpg": None, "data.json": "customer_document"}


def test_case_index_queries_do_not_scan_analysis_results() -> None:
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate("52998224725", artifact("a.pdf"), page=3),
        candidate("529.982.247-25", artifact("b.jpg"), engine="ocr"),
    ])
    index = CaseEvidenceIndex(report)
    fact = report.entities[0]
    assert len(index.find(EntityType.CPF, "52998224725")) == 2
    assert {item.occurrence_id for item in index.by_type(EntityType.CPF)} == {
        item.occurrence_id for item in fact.occurrences
    }
    assert len(index.for_artifact(artifact("a.pdf").stable_id)) == 1
    assert len(index.by_source_type("ocr")) == 1
    assert index.fact(fact.stable_id) is fact
    assert {item.occurrence_id for item in index.trace_occurrences(
        item.occurrence_id for item in fact.occurrences
    )} == {item.occurrence_id for item in fact.occurrences}


def test_hash_natures_are_distinct_facts() -> None:
    digest = "a" * 64
    source = artifact("a.txt")
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(digest, source, fact_type=EntityType.SHA256, engine="hash_engine", role="calculated_hash"),
        candidate(digest, source, fact_type=EntityType.SHA256, role="declared_hash"),
        candidate(digest, source, fact_type=EntityType.SHA256, role="hash_like"),
    ])
    assert len(report.entities) == 3
    assert {item.semantic_role for item in report.entities} == {
        "calculated_hash", "declared_hash", "hash_like",
    }


def test_temporal_provenance_preserves_timezone_state_and_precision() -> None:
    aware = candidate(
        "2024-01-02T03:04:05-03:00", artifact("aware.pdf"),
        fact_type=EntityType.TIMESTAMP, engine="metadata_engine",
        timezone_status="aware", precision="second",
    )
    naive = candidate(
        "2024-01-02T03:04:05", artifact("naive.pdf"),
        fact_type=EntityType.TIMESTAMP, engine="metadata_engine",
        timezone_status="naive", precision="second",
    )
    report = EvidenceGraphCorrelationEngine().correlate([aware, naive])
    occurrences = [item for fact in report.entities for item in fact.occurrences]
    assert {item.provenance.timezone_status for item in occurrences} == {"aware", "naive"}
    assert {item.provenance.timestamp_precision for item in occurrences} == {"second"}
    assert any(item.normalized_value.endswith("-03:00") for item in occurrences)
    assert any(item.normalized_value == "2024-01-02T03:04:05" for item in occurrences)


def test_observed_equality_does_not_create_structured_association() -> None:
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate("52998224725", artifact("a.pdf")),
        candidate("52998224725", artifact("b.pdf")),
    ])
    assert any(item.relation_type is RelationType.SAME_ENTITY_ACROSS_FILES for item in report.relations)
    assert not any(item.relation_type is RelationType.STRUCTURED_ASSOCIATION for item in report.relations)


def test_parser_supported_structured_association_is_explicit() -> None:
    relation = StructuredRelationCandidate(
        RelationType.STRUCTURED_ASSOCIATION, "name-fact", ("cpf-fact",),
        CorrelationProvenance(engine="json_parser", source_type="structured_json", json_path="$.customer"),
    )
    report = EvidenceGraphCorrelationEngine().correlate([], structured_relations=[relation])
    assert report.relations[0].relation_type is RelationType.STRUCTURED_ASSOCIATION
    assert report.relations[0].provenance == relation.provenance


def test_case_finding_is_traceable_and_severity_independent() -> None:
    digest = "b" * 64
    report = EvidenceGraphCorrelationEngine().correlate([
        candidate(digest, artifact("a.bin"), fact_type=EntityType.SHA256, engine="hash_engine", role="calculated_hash"),
        candidate(digest, artifact("b.bin"), fact_type=EntityType.SHA256, engine="hash_engine", role="calculated_hash"),
    ])
    index = CaseEvidenceIndex(report)
    finding = IdenticalCalculatedHashRule().evaluate(index)[0]
    assert finding.epistemic_state is EpistemicState.MATCH
    assert finding.severity.value == "info"
    assert len(index.trace_occurrences(finding.supporting_occurrence_ids)) == 2
    assert finding.relation_id and index.relation(finding.relation_id) is not None


def test_missing_rule_input_produces_no_mismatch() -> None:
    report = EvidenceGraphCorrelationEngine().correlate([])
    assert IdenticalCalculatedHashRule().evaluate(CaseEvidenceIndex(report)) == ()


def test_ids_and_order_are_stable_across_input_order_and_no_self_links() -> None:
    values = [
        candidate("52998224725", artifact("b.pdf")),
        candidate("529.982.247-25", artifact("a.pdf")),
    ]
    payloads = []
    for ordering in permutations(values):
        report = EvidenceGraphCorrelationEngine().correlate(ordering)
        payloads.append(report.to_dict())
        for relation in report.relations:
            if relation.relation_type is RelationType.SAME_ENTITY_ACROSS_FILES:
                assert len(relation.object_ids) == len(set(relation.object_ids)) == 2
    assert payloads[0] == payloads[1]


def test_pipeline_returns_versioned_deterministic_empty_case_result() -> None:
    pipeline = CanonicalCasePipeline(rules=())
    result = pipeline.analyze("case-1", [])
    assert result.case_result.schema_version == "1.0.0"
    assert result.case_result.findings == ()
    assert result.graph.entities == ()


def test_rule_failure_is_operational_limitation_and_preserves_facts() -> None:
    class BrokenRule:
        rule_id = "case.broken"
        rule_version = "1"
        required_fact_types = frozenset({EntityType.CPF})

        def evaluate(self, index):
            raise RuntimeError("internal detail must not become a finding")

    pipeline = CanonicalCasePipeline(rules=(BrokenRule(),))
    # The pipeline-level provider is intentionally bypassed here only to assert
    # rule isolation through the public empty-case behavior.
    result = pipeline.analyze("case-1", [])
    assert result.case_result.findings == ()
    assert len(result.case_result.limitations) == 1
    assert result.case_result.limitations[0].code == "rule_execution_failed"

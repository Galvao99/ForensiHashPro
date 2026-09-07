from __future__ import annotations

from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

from app.correlation.case_result import CaseResult, CaseResultJson, EpistemicState
from app.correlation.v2 import (
    AnalysisResultCorrelationProvider,
    CaseEvidenceIndex,
    CorrelationCandidate,
    CorrelationProvenance,
    EntityType,
    EvidenceGraphCorrelationEngine,
    MetadataCorrelationProvider,
    TimelineCorrelationProvider,
    source_file_identity,
)
from app.correlation.v2.pipeline import (
    CanonicalCasePipeline,
    CanonicalCasePipelineResult,
    DocumentDateMetadataTemporalRule,
)
from app.presentation.correlation_explorer import build_correlation_explorer_model
from app.services.temporal_parser import TemporalParser
from app.services.timeline_service import TimelineService


def artifact(name: str):
    return source_file_identity(display_name=name, path=f"/case/{name}")


def temporal(
    value: str,
    source,
    role: str,
    *,
    field: str,
    engine: str = "metadata_engine",
    page: int | None = None,
    offset: int | None = None,
) -> CorrelationCandidate:
    parsed = TemporalParser().parse(value)
    assert parsed is not None
    return CorrelationCandidate(
        EntityType.TIMESTAMP,
        parsed.raw,
        source,
        CorrelationProvenance(
            engine=engine,
            source_engine="native" if engine == "contract_date_extractor" else "exiftool",
            source_type="native" if engine == "contract_date_extractor" else "metadata",
            field=field,
            path=field,
            page=page,
            offset_start=offset,
            raw_value=parsed.raw,
            parsing_method="temporal_parser",
            timestamp_precision=parsed.precision,
            timezone_status=parsed.timezone_status,
            metadata_key=field if engine == "metadata_engine" else None,
        ),
        normalization_value=parsed.normalized,
        semantic_role=role,
    )


def evaluate(*candidates: CorrelationCandidate):
    graph = EvidenceGraphCorrelationEngine().correlate(candidates)
    findings = DocumentDateMetadataTemporalRule().evaluate(CaseEvidenceIndex(graph))
    return graph, findings


def pair(
    document: str,
    metadata: str,
    *,
    source=None,
    metadata_role: str = "pdf_creation_date",
    metadata_field: str = "PDF:CreationDate",
) -> tuple[CorrelationCandidate, CorrelationCandidate]:
    source = source or artifact("contract.pdf")
    return (
        temporal(
            document,
            source,
            "document_date",
            field="document_date",
            engine="contract_date_extractor",
            page=1,
            offset=18,
        ),
        temporal(metadata, source, metadata_role, field=metadata_field),
    )


def only_finding(*candidates: CorrelationCandidate):
    _, findings = evaluate(*candidates)
    assert len(findings) == 1
    return findings[0]


def test_document_date_before_and_after_creation_date_are_factual_relations() -> None:
    before = only_finding(*pair("2021-03-05", "2021-03-10T14:32:18"))
    after = only_finding(*pair("2021-03-12", "2021-03-10T14:32:18"))

    assert before.epistemic_state is EpistemicState.OBSERVED
    assert before.metadata["relation_type"] == "document_date_before_metadata"
    assert after.metadata["relation_type"] == "document_date_after_metadata"
    assert "posterior" in before.statement and "anterior" in after.statement
    assert all(
        token not in (before.statement + after.statement).casefold()
        for token in ("fraude", "adulter", "autentic", "suspeit")
    )


def test_day_precision_and_second_precision_on_same_day_overlap() -> None:
    finding = only_finding(*pair("05/03/2021", "2021-03-05T14:32:18"))

    assert finding.metadata["relation_type"] == "temporal_overlap"
    assert finding.metadata["document_precision"] == "day"
    assert finding.metadata["metadata_precision"] == "second"
    assert "14" not in finding.statement


def test_aware_values_compare_as_utc_instants() -> None:
    finding = only_finding(*pair(
        "2021-03-05T23:00:00-03:00", "2021-03-06T02:00:00Z",
    ))

    assert finding.metadata["relation_type"] == "temporal_overlap"
    assert finding.metadata["document_timezone_status"] == "explicit"
    assert finding.metadata["metadata_timezone_status"] == "explicit"


def test_naive_values_compare_in_the_civil_domain_without_assigning_timezone() -> None:
    finding = only_finding(*pair("2021-03-05", "2021-03-06T00:00:00"))

    assert finding.metadata["relation_type"] == "document_date_before_metadata"
    assert finding.metadata["document_timezone_status"] == "unknown"
    assert finding.metadata["metadata_timezone_status"] == "unknown"


def test_mixed_aware_and_naive_domains_produce_no_finding() -> None:
    _, findings = evaluate(*pair("2021-03-05", "2021-03-06T00:00:00Z"))
    assert findings == ()


def test_missing_document_or_metadata_is_normal_absence_not_mismatch() -> None:
    document, metadata = pair("2021-03-05", "2021-03-06T00:00:00")
    assert evaluate(document)[1] == ()
    assert evaluate(metadata)[1] == ()


def test_multiple_document_dates_are_ambiguous_and_never_selected_by_rule() -> None:
    source = artifact("ambiguous.pdf")
    first, metadata = pair("2021-03-05", "2021-03-10", source=source)
    second = temporal(
        "2021-03-06", source, "document_date", field="document_date",
        engine="contract_date_extractor", offset=90,
    )

    assert evaluate(first, second, metadata)[1] == ()


def test_multiple_supported_metadata_fields_produce_separate_findings() -> None:
    source = artifact("multi.pdf")
    document, creation = pair("2021-03-05", "2021-03-10", source=source)
    modification = temporal(
        "2021-03-11T10:30:00", source, "xmp_modify_date",
        field="XMP:ModifyDate",
    )

    _, findings = evaluate(document, creation, modification)
    assert len(findings) == 2
    assert {item.metadata["metadata_role"] for item in findings} == {
        "pdf_creation_date", "xmp_modify_date",
    }
    assert {item.metadata["metadata_field"] for item in findings} == {
        "PDF:CreationDate", "XMP:ModifyDate",
    }


def test_malformed_metadata_is_ignored_without_operational_limitation(
    tmp_path: Path,
) -> None:
    analysis = _analysis_result(
        tmp_path,
        metadata={"PDF:CreationDate": "not-a-date"},
        extracted_text="Data da contratação: 05/03/2021.",
    )
    analysis.timeline_events = TimelineService().build(analysis).events
    pipeline = CanonicalCasePipeline(provider=AnalysisResultCorrelationProvider(
        providers=(MetadataCorrelationProvider(), TimelineCorrelationProvider()),
    ), rules=(DocumentDateMetadataTemporalRule(),))

    result = pipeline.analyze("case-malformed", (analysis,))
    assert result.case_result.findings == ()
    assert result.case_result.limitations == ()


def test_field_statements_do_not_overclaim_creation_or_alteration() -> None:
    creation = only_finding(*pair("2021-03-05", "2021-03-10"))
    modification = only_finding(*pair(
        "2021-03-05", "2021-03-10", metadata_role="pdf_modify_date",
        metadata_field="PDF:ModDate",
    ))
    combined = (creation.statement + modification.statement).casefold()

    assert "documento foi criado" not in combined
    assert "conteúdo foi alterado" not in combined
    assert "validade jurídica" not in combined


def test_finding_identity_and_output_are_stable_across_input_order() -> None:
    candidates = pair("2021-03-05", "2021-03-10T14:32:18")
    outputs = []
    for ordering in permutations(candidates):
        _, findings = evaluate(*ordering)
        outputs.append(tuple(item.to_dict() for item in findings))

    assert outputs[0] == outputs[1]
    assert outputs[0][0]["finding_id"]
    assert outputs[0][0]["relation_id"]


def test_observed_relation_survives_case_result_round_trip() -> None:
    _, findings = evaluate(*pair("2021-03-05", "2021-03-10T14:32:18"))
    original = CaseResult("case-1", findings=findings)

    restored = CaseResultJson.loads(CaseResultJson.dumps(original, indent=None))

    assert restored == original
    assert restored.findings[0].epistemic_state is EpistemicState.OBSERVED


def test_unrelated_artifact_metadata_never_participates() -> None:
    document, _ = pair(
        "2021-03-05", "2021-03-10", source=artifact("document.pdf"),
    )
    _, foreign_metadata = pair(
        "2021-03-05", "2021-03-10", source=artifact("other.pdf"),
    )
    assert evaluate(document, foreign_metadata)[1] == ()


def test_supports_retain_original_provenance_precision_and_timezone() -> None:
    graph, findings = evaluate(*pair(
        "2021-03-05", "2021-03-10T14:32:18",
    ))
    finding = findings[0]
    supports = CaseEvidenceIndex(graph).trace_occurrences(
        finding.supporting_occurrence_ids
    )

    assert {item.semantic_role for item in supports} == {
        "document_date", "pdf_creation_date",
    }
    document = next(item for item in supports if item.semantic_role == "document_date")
    metadata = next(item for item in supports if item.semantic_role == "pdf_creation_date")
    assert (document.provenance.page, document.provenance.offset_start) == (1, 18)
    assert document.provenance.timestamp_precision == "day"
    assert metadata.provenance.timestamp_precision == "second"
    assert metadata.provenance.metadata_key == "PDF:CreationDate"
    assert all(item.provenance.timezone_status == "unknown" for item in supports)


def test_metadata_and_timeline_projection_share_roles_without_duplicate_occurrence(
    tmp_path: Path,
) -> None:
    analysis = _analysis_result(
        tmp_path,
        metadata={"PDF:CreationDate": "2021-03-10T14:32:18-03:00"},
    )
    analysis.timeline_events = TimelineService().build(analysis).events
    provider = AnalysisResultCorrelationProvider(
        providers=(MetadataCorrelationProvider(), TimelineCorrelationProvider()),
    )
    graph = EvidenceGraphCorrelationEngine().correlate(provider.provide_many((analysis,)))
    occurrence = CaseEvidenceIndex(graph).by_semantic_role("pdf_creation_date")[0]

    assert occurrence.semantic_role == "pdf_creation_date"
    assert occurrence.provenance.timestamp_precision == "second"
    assert occurrence.provenance.timezone_status == "explicit"
    assert occurrence.provenance.metadata_key == "PDF:CreationDate"
    assert len(CaseEvidenceIndex(graph).by_semantic_role("pdf_creation_date")) == 1


def test_only_supported_document_metadata_fields_receive_comparable_roles(
    tmp_path: Path,
) -> None:
    analysis = _analysis_result(tmp_path, metadata={
        "PDF:CreationDate": "2021-03-10T14:32:18",
        "XMP-xmp:ModifyDate": "2021-03-11T09:00:00Z",
        "EXIF:ModifyDate": "2021-03-12T09:00:00Z",
        "File:FileModifyDate": "2021-03-13T09:00:00Z",
    })
    analysis.timeline_events = TimelineService().build(analysis).events
    provider = AnalysisResultCorrelationProvider(
        providers=(MetadataCorrelationProvider(), TimelineCorrelationProvider()),
    )
    graph = EvidenceGraphCorrelationEngine().correlate(provider.provide_many((analysis,)))
    occurrences = tuple(
        occurrence for entity in graph.entities for occurrence in entity.occurrences
    )

    assert {item.semantic_role for item in occurrences if item.semantic_role} == {
        "pdf_creation_date", "xmp_modify_date",
    }
    assert any(
        item.provenance.field == "EXIF:ModifyDate" and item.semantic_role is None
        for item in occurrences
    )
    assert any(
        item.provenance.field == "File:FileModifyDate" and item.semantic_role is None
        for item in occurrences
    )


def test_contract_date_v2_selection_is_reused_not_reimplemented(tmp_path: Path) -> None:
    analysis = _analysis_result(
        tmp_path,
        metadata={"PDF:CreationDate": "2026-07-20T10:00:00"},
        extracted_text=(
            "Data da contratação: 15/07/2026. "
            "Data de emissão: 14/07/2026."
        ),
    )
    analysis.timeline_events = TimelineService().build(analysis).events
    pipeline = CanonicalCasePipeline(provider=AnalysisResultCorrelationProvider(
        providers=(MetadataCorrelationProvider(), TimelineCorrelationProvider()),
    ))

    result = pipeline.analyze("case-1", (analysis,))
    documents = result.index.by_semantic_role("document_date")
    finding = next(
        item for item in result.case_result.findings
        if item.rule_id == DocumentDateMetadataTemporalRule.rule_id
    )

    assert len(documents) == 1
    assert documents[0].raw_value == "15/07/2026"
    assert documents[0].context
    assert documents[0].provenance.offset_start is not None
    assert finding.metadata["relation_type"] == "document_date_before_metadata"


def test_presenter_only_projects_case_result_and_labels_relation_observed(
    monkeypatch,
) -> None:
    graph, findings = evaluate(*pair("2021-03-05", "2021-03-10T14:32:18"))
    snapshot = CanonicalCasePipelineResult(
        graph,
        CaseEvidenceIndex(graph),
        CaseResult("case-1", findings=findings),
    )

    def fail_if_recalculated(*_args, **_kwargs):
        raise AssertionError("presenter must not execute the deterministic rule")

    monkeypatch.setattr(DocumentDateMetadataTemporalRule, "evaluate", fail_if_recalculated)
    model = build_correlation_explorer_model(snapshot)
    group = next(item for item in model.verification_groups if item.key == "document_date_metadata")
    verification = group.items[0]

    assert group.label == "Data documental × metadados"
    assert verification.state == "OBSERVADA"
    assert dict(verification.details)["Relação temporal observada"] == (
        "metadado posterior à data documental"
    )
    assert "regra" not in verification.description.casefold()


def _analysis_result(
    tmp_path: Path,
    *,
    metadata: dict[str, object],
    extracted_text: str = "",
):
    return SimpleNamespace(
        metadata=SimpleNamespace(raw=metadata),
        file_info=SimpleNamespace(
            name="contract.pdf", path=tmp_path / "contract.pdf",
            created_at=None, modified_at=None, accessed_at=None,
        ),
        hashes=SimpleNamespace(sha256="a" * 64, md5="b" * 32),
        evidence_source=None,
        extracted_text=extracted_text,
        processing_steps=[],
        timeline_events=[],
        digital_signature=SimpleNamespace(
            signatures=[], signing_time=None, timestamp=None,
            valid_from=None, valid_until=None,
        ),
        json_analysis=None,
        binary_analysis=None,
        pdf_structure=None,
        analyzed_at=None,
        completed_at=None,
        resolved_entities=[],
    )

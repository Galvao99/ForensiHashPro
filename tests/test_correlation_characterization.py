from __future__ import annotations

from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.correlation.v2 import (
    CorrelationCandidate,
    CorrelationProvenance,
    EntityType as GraphEntityType,
    EvidenceGraphCorrelationEngine,
    RelationType,
    source_file_identity,
)
from app.entities import EntitySource, EntitySourceType, EntityType, NormalizedEntity
from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.declared_hash import DeclaredHashExtractor, DeclaredHashOccurrence
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.embedded_hash_match_rule import EmbeddedHashMatchRule
from app.investigation.rules.embedded_hash_unmatched_rule import EmbeddedHashUnmatchedRule
from app.investigation.rules.entity_correlation_rule import EntityCorrelationRule
from app.services.correlation_service import CorrelationService


CPF_X = "52998224725"
CPF_Y = "11144477735"


def _entity(
    value: str,
    *,
    evidence_ref: str,
    role_text: str = "CPF cliente:",
    source_type: EntitySourceType = EntitySourceType.NATIVE_TEXT,
    entity_type: EntityType = EntityType.CPF,
    page: int = 1,
    start: int = 4,
) -> NormalizedEntity:
    return NormalizedEntity(
        entity_type=entity_type,
        normalized_value=value,
        confidence=0.95,
        raw_values=(value,),
        sources=(
            EntitySource(
                source_type=source_type,
                source_file=evidence_ref,
                page=page,
                start=start,
                end=start + len(value),
                context_before=role_text,
                extractor=f"{source_type.value}_extractor",
                field_path=("$.customer.cpf" if source_type is EntitySourceType.JSON else None),
            ),
        ),
    )


def _entity_context(
    ordered_items: tuple[tuple[str, str, tuple[NormalizedEntity, ...]], ...]
) -> InvestigationContext:
    context = InvestigationContext()
    for key, filename, entities in ordered_items:
        context.display_names[key] = filename
        context.resolved_entities[key] = list(entities)
    return context


def _relation_signature(finding) -> tuple[object, ...]:
    return (
        finding.rule_id,
        finding.category,
        finding.source_evidence_key or finding.source_file,
        finding.target_evidence_key or finding.target_file,
        tuple(
            sorted(
                (
                    item.evidence_ref,
                    item.source_type,
                    item.page,
                    item.start,
                    item.field_path,
                    item.normalized_value,
                )
                for item in finding.evidence
            )
        ),
        tuple(
            sorted(
                (item.entity_type, item.normalized_value, item.role)
                for item in finding.entities
            )
        ),
        finding.metadata.get("semantic_role"),
        finding.metadata.get("algorithm"),
        finding.metadata.get("hash"),
    )


def _undirected_signature(finding) -> tuple[object, ...]:
    source = finding.source_evidence_key or finding.source_file
    target = finding.target_evidence_key or finding.target_file
    endpoints = tuple(sorted(item for item in (source, target) if item is not None))
    return finding.rule_id, finding.category, endpoints


def _declared(
    value: str,
    *,
    source: str = "ev-a",
    filename: str = "A.pdf",
    algorithm: str = "SHA-256",
    hint: str | None = None,
) -> DeclaredHashOccurrence:
    return DeclaredHashOccurrence(
        value=value,
        algorithm=algorithm,
        evidence_ref=source,
        filename=filename,
        source_type="native_text",
        page=2,
        start=20,
        end=20 + len(value),
        field_path="page[2].text",
        context=f"Hash do {hint}: {value}" if hint else f"{algorithm}: {value}",
        artifact_hint=hint,
        declared=True,
    )


def _hash_context(
    calculated: tuple[tuple[str, str, str], ...],
    declared: tuple[tuple[str, DeclaredHashOccurrence], ...] = (),
) -> InvestigationContext:
    context = InvestigationContext()
    for key, filename, value in calculated:
        context.display_names[key] = filename
        context.calculated_hashes[key] = {
            "SHA-256": value,
        }
    for key, occurrence in declared:
        context.declared_hashes.setdefault(key, []).append(occurrence)
    return context


def _legacy_result(path: Path, *, sha256: str, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        file_info=SimpleNamespace(name=path.name, path=path),
        extracted_text=text,
        hashes=SimpleNamespace(sha256=sha256),
        metadata=SimpleNamespace(raw={}),
        digital_signature=None,
        timeline_events=[],
        processing_steps=[],
        resolved_entities=[],
        json_analysis=None,
    )


def test_entity_three_file_match_has_three_pairs_but_direction_follows_input_order() -> None:
    """Known characterization: the relation set is stable, endpoint direction is not."""
    artifacts = (
        ("ev-a", "A.pdf", (_entity(CPF_X, evidence_ref="ev-a"),)),
        ("ev-b", "B.pdf", (_entity(CPF_X, evidence_ref="ev-b"),)),
        ("ev-c", "C.pdf", (_entity(CPF_X, evidence_ref="ev-c"),)),
    )
    undirected_results = set()
    directed_results = set()
    finding_id_results = set()
    for ordering in permutations(artifacts):
        result = CorrelationEngine([EntityCorrelationRule()]).evaluate(
            _entity_context(ordering)
        )
        assert len(result.findings) == 3
        assert {item.rule_id for item in result.findings} == {"entity_match"}
        assert all(item.metadata["semantic_role"] == "customer" for item in result.findings)
        assert all(len(item.evidence) == 2 for item in result.findings)
        undirected_results.add(
            tuple(sorted(_undirected_signature(item) for item in result.findings))
        )
        directed_results.add(
            tuple(sorted(_relation_signature(item) for item in result.findings))
        )
        finding_id_results.add(tuple(sorted(item.finding_id for item in result.findings)))

    assert len(undirected_results) == 1
    assert len(directed_results) > 1
    assert len(finding_id_results) > 1


def test_entity_mismatch_and_different_roles_preserve_current_semantics() -> None:
    comparable = _entity_context(
        (
            ("ev-a", "A.pdf", (_entity(CPF_X, evidence_ref="ev-a"),)),
            ("ev-b", "B.pdf", (_entity(CPF_Y, evidence_ref="ev-b"),)),
        )
    )
    mismatch = CorrelationEngine([EntityCorrelationRule()]).evaluate(comparable)
    assert len(mismatch.findings) == 1
    finding = mismatch.findings[0]
    assert (finding.rule_id, finding.category) == ("entity_mismatch", "entity_mismatch")
    assert (finding.source_evidence_key, finding.target_evidence_key) == ("ev-a", "ev-b")
    assert {item.normalized_value for item in finding.evidence} == {CPF_X, CPF_Y}
    assert finding.metadata["semantic_role"] == "customer"

    different_roles = _entity_context(
        (
            ("ev-a", "A.pdf", (_entity(CPF_X, evidence_ref="ev-a"),)),
            (
                "ev-b",
                "B.pdf",
                (_entity(CPF_Y, evidence_ref="ev-b", role_text="CPF:"),),
            ),
        )
    )
    assert CorrelationEngine([EntityCorrelationRule()]).evaluate(different_roles).findings == []


def test_legacy_dedup_characterization_collapses_distinct_entity_evidence() -> None:
    """Known legacy limitation: one of two independent provenances is discarded."""
    native = _entity(CPF_X, evidence_ref="ev-a", source_type=EntitySourceType.NATIVE_TEXT)
    structured = _entity(
        CPF_X,
        evidence_ref="ev-a",
        source_type=EntitySourceType.JSON,
        page=3,
        start=11,
    )
    target = _entity(CPF_X, evidence_ref="ev-b")
    context = _entity_context(
        (
            ("ev-a", "A.pdf", (native, structured)),
            ("ev-b", "B.pdf", (target,)),
        )
    )

    before_dedup = EntityCorrelationRule().evaluate(context)
    after_dedup = CorrelationEngine([EntityCorrelationRule()]).evaluate(context).findings

    assert len(before_dedup) == 2
    assert {item.evidence[0].source_type for item in before_dedup} == {
        "native_text",
        "json",
    }
    assert len(after_dedup) == 1
    assert [item.source_type for item in after_dedup[0].evidence] == [
        "native_text",
        "native_text",
    ]


@pytest.mark.parametrize(
    ("left", "right", "expected"),
    [("1234.56", "1234.56", "entity_match"), ("1234.56", "999.00", "entity_mismatch")],
)
def test_money_entities_with_same_semantic_role_are_compared(
    left: str, right: str, expected: str
) -> None:
    context = _entity_context(
        (
            (
                "ev-a",
                "A.pdf",
                (
                    _entity(
                        left,
                        evidence_ref="ev-a",
                        role_text="Valor da parcela:",
                        entity_type=EntityType.MONEY,
                    ),
                ),
            ),
            (
                "ev-b",
                "B.pdf",
                (
                    _entity(
                        right,
                        evidence_ref="ev-b",
                        role_text="Valor da parcela:",
                        entity_type=EntityType.MONEY,
                    ),
                ),
            ),
        )
    )
    result = CorrelationEngine([EntityCorrelationRule()]).evaluate(context)
    assert len(result.findings) == 1
    assert result.findings[0].category == expected
    assert result.findings[0].metadata["semantic_role"] == "installment"


def test_embedded_hash_match_forbids_self_link_and_preserves_multiple_targets() -> None:
    value = "b" * 64
    context = _hash_context(
        (
            ("ev-a", "A.pdf", value),
            ("ev-b", "B.bin", value),
            ("ev-c", "C.bin", value),
        ),
        (("ev-a", _declared(value)),),
    )
    result = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context)
    declared_matches = [
        item for item in result.findings if item.category == "embedded_hash_match"
    ]

    assert len(declared_matches) == 2
    assert {(item.source_evidence_key, item.target_evidence_key) for item in declared_matches} == {
        ("ev-a", "ev-b"),
        ("ev-a", "ev-c"),
    }
    assert all(len(item.evidence) == 2 for item in declared_matches)
    assert all(item.metadata["match_type"] == "exact_cryptographic_match" for item in declared_matches)
    assert not any(
        item.source_evidence_key == item.target_evidence_key for item in declared_matches
    )


def test_embedded_hash_match_preserves_multiple_declarants() -> None:
    value = "c" * 64
    context = _hash_context(
        (
            ("ev-a", "A.pdf", "a" * 64),
            ("ev-d", "D.pdf", "d" * 64),
            ("ev-b", "B.bin", value),
        ),
        (
            ("ev-a", _declared(value, source="ev-a", filename="A.pdf")),
            ("ev-d", _declared(value, source="ev-d", filename="D.pdf")),
        ),
    )
    result = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context)
    matches = [item for item in result.findings if item.category == "embedded_hash_match"]
    assert len(matches) == 2
    assert {(item.source_evidence_key, item.target_evidence_key) for item in matches} == {
        ("ev-a", "ev-b"),
        ("ev-d", "ev-b"),
    }


@pytest.mark.parametrize(
    ("algorithm", "length"),
    [
        ("MD5", 32),
        ("SHA-1", 40),
        ("SHA-224", 56),
        ("SHA-256", 64),
        ("SHA-384", 96),
        ("SHA-512", 128),
    ],
)
def test_declared_hash_algorithms_match_calculated_values(
    algorithm: str, length: int
) -> None:
    value = "a" * length
    occurrence = DeclaredHashExtractor().extract_text(
        f"{algorithm}: {value}",
        evidence_ref="ev-a",
        filename="A.pdf",
        source_type="native_text",
        page=1,
    )[0]
    context = InvestigationContext(
        display_names={"ev-a": "A.pdf", "ev-b": "B.bin"},
        calculated_hashes={"ev-a": {"SHA-256": "f" * 64}, "ev-b": {algorithm: value}},
        declared_hashes={"ev-a": [occurrence]},
    )
    findings = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context).findings
    match = next(item for item in findings if item.category == "embedded_hash_match")
    assert match.metadata == {
        "algorithm": algorithm,
        "hash": value,
        "source_file": "A.pdf",
        "matched_file": "B.bin",
        "calculated_hash": value,
        "match_type": "exact_cryptographic_match",
    }


def test_hash_permutations_preserve_relations_but_cross_file_direction_is_order_dependent() -> None:
    value = "d" * 64
    calculated = (
        ("ev-a", "A.pdf", "a" * 64),
        ("ev-b", "B.bin", value),
        ("ev-c", "C.bin", value),
    )
    declared_relations = set()
    cross_undirected = set()
    cross_directed = set()
    cross_finding_ids = set()
    for ordering in permutations(calculated):
        context = _hash_context(ordering, (("ev-a", _declared(value)),))
        findings = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context).findings
        declared_relations.add(
            tuple(
                sorted(
                    (item.source_evidence_key, item.target_evidence_key)
                    for item in findings
                    if item.category == "embedded_hash_match"
                )
            )
        )
        cross = [item for item in findings if item.category == "cross_file_match"]
        cross_undirected.add(tuple(sorted(_undirected_signature(item) for item in cross)))
        cross_directed.add(
            tuple(
                sorted(
                    (item.source_evidence_key, item.target_evidence_key) for item in cross
                )
            )
        )
        cross_finding_ids.add(tuple(sorted(item.finding_id for item in cross)))

    assert len(declared_relations) == 1
    assert len(cross_undirected) == 1
    assert len(cross_directed) > 1
    assert len(cross_finding_ids) > 1


def test_unmatched_hash_distinguishes_missing_target_from_explicit_mismatch() -> None:
    missing_value = "e" * 64
    missing = _hash_context(
        (("ev-a", "Contrato.pdf", "a" * 64),),
        (("ev-a", _declared(missing_value, filename="Contrato.pdf")),),
    )
    missing_result = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(missing)
    assert len(missing_result.findings) == 1
    absent = missing_result.findings[0]
    assert (absent.rule_id, absent.category) == (
        "embedded_hash_unmatched",
        "embedded_hash_unmatched",
    )
    assert absent.source_evidence_key == "ev-a"
    assert absent.target_evidence_key is None
    assert len(absent.evidence) == 1
    assert absent.limitations == [
        "O artefato correspondente pode simplesmente não integrar este Analysis Set."
    ]

    mismatch = _hash_context(
        (
            ("ev-a", "Contrato.pdf", "a" * 64),
            ("ev-b", "anexo.pdf", "f" * 64),
        ),
        (
            (
                "ev-a",
                _declared(
                    missing_value,
                    filename="Contrato.pdf",
                    hint="anexo.pdf",
                ),
            ),
        ),
    )
    mismatch_result = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(mismatch)
    assert len(mismatch_result.findings) == 1
    divergent = mismatch_result.findings[0]
    assert (divergent.rule_id, divergent.category) == (
        "declared_hash_mismatch",
        "declared_hash_mismatch",
    )
    assert (divergent.source_evidence_key, divergent.target_evidence_key) == (
        "ev-a",
        "ev-b",
    )
    assert len(divergent.evidence) == 2
    assert divergent.limitations == []
    assert "difere do hash calculado" in divergent.description


def test_unmatched_hash_result_is_order_independent_for_current_scenarios() -> None:
    value = "e" * 64
    calculated = (
        ("ev-a", "Contrato.pdf", "a" * 64),
        ("ev-b", "anexo.pdf", "f" * 64),
        ("ev-c", "outro.bin", "c" * 64),
    )
    results = set()
    for ordering in permutations(calculated):
        context = _hash_context(
            ordering,
            (("ev-a", _declared(value, filename="Contrato.pdf", hint="anexo.pdf")),),
        )
        findings = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(context).findings
        results.add(tuple(_relation_signature(item) for item in findings))
    assert len(results) == 1


def test_case_full_rebuild_incremental_and_remove_readd_are_equivalent(
    tmp_path: Path,
) -> None:
    value = "b" * 64
    artifacts = (
        _legacy_result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}"),
        _legacy_result(tmp_path / "B.bin", sha256=value),
        _legacy_result(tmp_path / "C.bin", sha256=value),
    )
    rebuilt = CorrelationService().update_case("full", list(reversed(artifacts)))

    incremental_service = CorrelationService()
    incremental = None
    for artifact in artifacts:
        incremental = incremental_service.add_to_case("incremental", artifact)

    readd_service = CorrelationService()
    for artifact in artifacts:
        readd_service.add_to_case("readd", artifact)
    readd_service.remove_from_case("readd", artifacts[1].file_info.path)
    readded = readd_service.add_to_case("readd", artifacts[1])

    assert incremental is not None
    assert [_relation_signature(item) for item in rebuilt.findings] == [
        _relation_signature(item) for item in incremental.findings
    ] == [_relation_signature(item) for item in readded.findings]
    assert [item.finding_id for item in rebuilt.findings] == [
        item.finding_id for item in incremental.findings
    ] == [item.finding_id for item in readded.findings]


def test_legacy_and_v2_have_factual_equivalence_for_exact_entity_and_hash() -> None:
    entity_context = _entity_context(
        (
            ("ev-a", "A.pdf", (_entity(CPF_X, evidence_ref="ev-a"),)),
            ("ev-b", "B.pdf", (_entity(CPF_X, evidence_ref="ev-b"),)),
        )
    )
    legacy_entity = CorrelationEngine([EntityCorrelationRule()]).evaluate(entity_context)
    assert [item.category for item in legacy_entity.findings] == ["entity_match"]

    graph_a = source_file_identity(display_name="A.pdf", session_id="ev-a")
    graph_b = source_file_identity(display_name="B.pdf", session_id="ev-b")
    graph_entity = EvidenceGraphCorrelationEngine().correlate(
        (
            CorrelationCandidate(
                GraphEntityType.CPF,
                CPF_X,
                graph_a,
                CorrelationProvenance(engine="native_text", field="cpf"),
            ),
            CorrelationCandidate(
                GraphEntityType.CPF,
                CPF_X,
                graph_b,
                CorrelationProvenance(engine="native_text", field="cpf"),
            ),
        )
    )
    entity_relation = next(
        item
        for item in graph_entity.relations
        if item.relation_type is RelationType.SAME_ENTITY_ACROSS_FILES
    )
    assert set(entity_relation.object_ids) == {graph_a.stable_id, graph_b.stable_id}

    value = "f" * 64
    legacy_hash = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(
        _hash_context((("ev-a", "A.bin", value), ("ev-b", "B.bin", value)))
    )
    assert [item.category for item in legacy_hash.findings] == ["cross_file_match"]
    graph_hash = EvidenceGraphCorrelationEngine().correlate(
        (
            CorrelationCandidate(
                GraphEntityType.SHA256,
                value,
                graph_a,
                CorrelationProvenance(engine="hash_engine", field="sha256"),
            ),
            CorrelationCandidate(
                GraphEntityType.SHA256,
                value,
                graph_b,
                CorrelationProvenance(engine="hash_engine", field="sha256"),
            ),
        )
    )
    assert RelationType.SAME_HASH in {item.relation_type for item in graph_hash.relations}


def test_v2_has_no_factual_equivalent_for_mismatch_or_unmatched_semantics() -> None:
    legacy_mismatch = CorrelationEngine([EntityCorrelationRule()]).evaluate(
        _entity_context(
            (
                ("ev-a", "A.pdf", (_entity(CPF_X, evidence_ref="ev-a"),)),
                ("ev-b", "B.pdf", (_entity(CPF_Y, evidence_ref="ev-b"),)),
            )
        )
    )
    assert [item.category for item in legacy_mismatch.findings] == ["entity_mismatch"]

    graph_a = source_file_identity(display_name="A.pdf", session_id="ev-a")
    graph_b = source_file_identity(display_name="B.pdf", session_id="ev-b")
    graph = EvidenceGraphCorrelationEngine().correlate(
        (
            CorrelationCandidate(
                GraphEntityType.CPF,
                CPF_X,
                graph_a,
                CorrelationProvenance(engine="native_text"),
            ),
            CorrelationCandidate(
                GraphEntityType.CPF,
                CPF_Y,
                graph_b,
                CorrelationProvenance(engine="native_text"),
            ),
        )
    )
    assert RelationType.SAME_ENTITY_ACROSS_FILES not in {
        item.relation_type for item in graph.relations
    }
    assert not {"MISMATCH", "UNKNOWN"}.intersection(
        {item.value for item in RelationType}
    )

    missing = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(
        _hash_context(
            (("ev-a", "A.pdf", "a" * 64),),
            (("ev-a", _declared("b" * 64)),),
        )
    )
    assert [item.category for item in missing.findings] == ["embedded_hash_unmatched"]
    assert "DECLARED_HASH" not in {item.value for item in RelationType}

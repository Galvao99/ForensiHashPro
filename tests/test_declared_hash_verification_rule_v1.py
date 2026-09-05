from __future__ import annotations

from itertools import permutations
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.correlation.case_result import EpistemicState
from app.correlation.v2 import (
    AnalysisResultCorrelationProvider,
    CaseEvidenceIndex,
    CorrelationCandidate,
    CorrelationProvenance,
    DeclaredHashTargetCandidate,
    EntityType,
    EvidenceGraphCorrelationEngine,
    RelationType,
    source_file_identity,
)
from app.correlation.v2.pipeline import (
    CanonicalCasePipeline,
    DeclaredHashVerificationRule,
)
from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.declared_hash import DeclaredHashOccurrence
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.embedded_hash_match_rule import EmbeddedHashMatchRule
from app.investigation.rules.embedded_hash_unmatched_rule import EmbeddedHashUnmatchedRule
from app.models.json_analysis_result import JsonAnalysisResult, JsonField


def artifact(name: str, suffix: str = ""):
    return source_file_identity(display_name=name, path=f"/case/{suffix}{name}")


def hash_candidate(
    digest: str, source, role: str, *, algorithm: EntityType = EntityType.SHA256,
    path: str | None = None, engine: str | None = None,
) -> CorrelationCandidate:
    return CorrelationCandidate(
        algorithm, digest, source,
        CorrelationProvenance(
            engine=engine or ("hash_engine" if role == "calculated_hash" else "json_engine"),
            source_type=role, path=path, json_path=path, raw_value=digest,
        ), semantic_role=role,
    )


def evaluate(
    declared: CorrelationCandidate,
    calculated: list[CorrelationCandidate],
    *, bind: bool = True,
):
    bindings = (
        [DeclaredHashTargetCandidate(
            declared, calculated[0].source_file,
            CorrelationProvenance(
                engine="json_parser", source_type="structured_json",
                path="$.entry", json_path="$.entry",
            ),
        )]
        if bind and calculated else []
    )
    report = EvidenceGraphCorrelationEngine().correlate(
        [declared, *calculated], declared_hash_targets=bindings,
    )
    return report, DeclaredHashVerificationRule().evaluate(CaseEvidenceIndex(report))


def test_equal_bound_sha256_is_match_with_complete_trace() -> None:
    source, target = artifact("protocol.json"), artifact("contract.pdf")
    declared = hash_candidate("a" * 64, source, "declared_hash", path="$.entry.sha256")
    calculated = hash_candidate("a" * 64, target, "calculated_hash")
    report, findings = evaluate(declared, [calculated])
    finding = findings[0]
    assert finding.epistemic_state is EpistemicState.MATCH
    assert set(finding.supporting_occurrence_ids) == {
        item.occurrence_id for fact in report.entities for item in fact.occurrences
    }
    relation = CaseEvidenceIndex(report).relation(finding.relation_id or "")
    assert relation is not None
    assert relation.relation_type is RelationType.DECLARED_HASH_TARGET
    assert relation.subject_id in finding.supporting_occurrence_ids
    assert relation.object_ids == (target.stable_id,)


def test_different_bound_sha256_is_mismatch_without_forensic_overclaim() -> None:
    declared = hash_candidate("a" * 64, artifact("protocol.json"), "declared_hash")
    calculated = hash_candidate("b" * 64, artifact("contract.pdf"), "calculated_hash")
    _, findings = evaluate(declared, [calculated])
    finding = findings[0]
    assert finding.epistemic_state is EpistemicState.MISMATCH
    assert finding.severity.value == "info"
    assert not {"fraude", "adultera", "autênt"}.intersection(finding.statement.casefold().split())


@pytest.mark.parametrize("same", [True, False])
def test_digest_values_without_target_binding_do_not_verify(same: bool) -> None:
    declared = hash_candidate("a" * 64, artifact("protocol.json"), "declared_hash")
    calculated = hash_candidate(("a" if same else "b") * 64, artifact("contract.pdf"), "calculated_hash")
    _, findings = evaluate(declared, [calculated], bind=False)
    assert findings == ()


def test_hash_like_ocr_is_not_a_declaration() -> None:
    observed = hash_candidate(
        "a" * 64, artifact("scan.jpg"), "hash_like", engine="ocr",
    )
    calculated = hash_candidate("a" * 64, artifact("contract.pdf"), "calculated_hash")
    report = EvidenceGraphCorrelationEngine().correlate([observed, calculated])
    assert DeclaredHashVerificationRule().evaluate(CaseEvidenceIndex(report)) == ()
    with pytest.raises(ValueError, match="declared_hash"):
        DeclaredHashTargetCandidate(
            observed, calculated.source_file,
            CorrelationProvenance(engine="invalid_binding"),
        )


def test_md5_declaration_is_not_compared_with_sha256() -> None:
    declared = hash_candidate("a" * 32, artifact("protocol.json"), "declared_hash", algorithm=EntityType.MD5)
    calculated = hash_candidate("b" * 64, artifact("contract.pdf"), "calculated_hash")
    _, findings = evaluate(declared, [calculated])
    assert findings == ()


def test_missing_declared_or_calculated_hash_does_not_mismatch() -> None:
    calculated = hash_candidate("a" * 64, artifact("contract.pdf"), "calculated_hash")
    calculated_report = EvidenceGraphCorrelationEngine().correlate([calculated])
    assert DeclaredHashVerificationRule().evaluate(CaseEvidenceIndex(calculated_report)) == ()
    declared = hash_candidate("a" * 64, artifact("protocol.json"), "declared_hash")
    declared_report = EvidenceGraphCorrelationEngine().correlate([declared])
    assert DeclaredHashVerificationRule().evaluate(CaseEvidenceIndex(declared_report)) == ()


def json_result(filename: str, digest: str) -> JsonAnalysisResult:
    return JsonAnalysisResult(
        is_valid=True,
        fields=[
            JsonField("$.entry.filename", "filename", filename, "string"),
            JsonField("$.entry.sha256", "sha256", digest, "string"),
        ],
    )


def analysis(path: Path, digest: str, json: JsonAnalysisResult | None = None):
    return SimpleNamespace(
        file_info=SimpleNamespace(name=path.name, path=path),
        hashes=SimpleNamespace(sha256=digest, md5=""),
        evidence_source=None, resolved_entities=[], processing_steps=[],
        metadata=SimpleNamespace(raw={}), json_analysis=json, timeline_events=[],
    )


def test_exact_structured_filename_binding_resolves_unique_target(tmp_path: Path) -> None:
    digest = "c" * 64
    protocol = analysis(tmp_path / "protocol.json", "d" * 64, json_result("contract.pdf", digest))
    target = analysis(tmp_path / "contract.pdf", digest)
    result = CanonicalCasePipeline().analyze("case", [protocol, target])
    finding = next(
        item for item in result.case_result.findings
        if item.rule_id == "case.declared_hash_verification"
    )
    assert finding.epistemic_state is EpistemicState.MATCH
    relation = result.index.relation(finding.relation_id or "")
    assert relation and relation.provenance
    assert relation.provenance.json_path == "$.entry"
    assert relation.provenance.raw_value == "contract.pdf"


def test_ambiguous_exact_filename_does_not_guess(tmp_path: Path) -> None:
    digest = "c" * 64
    protocol = analysis(tmp_path / "protocol.json", "d" * 64, json_result("contract.pdf", digest))
    first = analysis(tmp_path / "one" / "contract.pdf", digest)
    second = analysis(tmp_path / "two" / "contract.pdf", digest)
    result = CanonicalCasePipeline().analyze("case", [protocol, first, second])
    assert not result.index.relations_by_type(RelationType.DECLARED_HASH_TARGET)
    assert not any(item.rule_id == "case.declared_hash_verification" for item in result.case_result.findings)


def test_similar_filename_does_not_bind(tmp_path: Path) -> None:
    protocol = analysis(tmp_path / "protocol.json", "d" * 64, json_result("contract.pdf", "c" * 64))
    target = analysis(tmp_path / "contract-final.pdf", "c" * 64)
    batch = AnalysisResultCorrelationProvider().provide_case([protocol, target])
    assert batch.declared_hash_targets == ()


def test_multiple_declarations_are_preserved_and_deterministic() -> None:
    source, target = artifact("manifest.json"), artifact("contract.pdf")
    declarations = [
        hash_candidate("a" * 64, source, "declared_hash", path="$.entries[0].sha256"),
        hash_candidate("b" * 64, source, "declared_hash", path="$.entries[1].sha256"),
    ]
    calculated = hash_candidate("a" * 64, target, "calculated_hash")
    outputs = []
    for ordered in permutations(declarations):
        bindings = [
            DeclaredHashTargetCandidate(
                item, target,
                CorrelationProvenance(engine="json_parser", path=item.provenance.path),
            ) for item in ordered
        ]
        report = EvidenceGraphCorrelationEngine().correlate(
            [*ordered, calculated], declared_hash_targets=bindings,
        )
        findings = DeclaredHashVerificationRule().evaluate(CaseEvidenceIndex(report))
        outputs.append(tuple(item.to_dict() for item in findings))
    assert outputs[0] == outputs[1]
    assert {item["epistemic_state"] for item in outputs[0]} == {"match", "mismatch"}


def test_identical_calculated_hashes_do_not_choose_target_without_binding() -> None:
    digest = "a" * 64
    declared = hash_candidate(digest, artifact("manifest.json"), "declared_hash")
    calculated = [
        hash_candidate(digest, artifact("a.bin"), "calculated_hash"),
        hash_candidate(digest, artifact("b.bin"), "calculated_hash"),
    ]
    report = EvidenceGraphCorrelationEngine().correlate([declared, *calculated])
    index = CaseEvidenceIndex(report)
    assert index.relations_by_type(RelationType.SAME_HASH)
    assert not index.relations_by_type(RelationType.DECLARED_HASH_TARGET)
    assert DeclaredHashVerificationRule().evaluate(index) == ()


def test_binding_rejects_self_link() -> None:
    source = artifact("manifest.json")
    declared = hash_candidate("a" * 64, source, "declared_hash")
    with pytest.raises(ValueError, match="itself"):
        DeclaredHashTargetCandidate(
            declared, source, CorrelationProvenance(engine="json_parser"),
        )


def test_legacy_match_characterization_has_no_target_binding() -> None:
    digest = "a" * 64
    context = InvestigationContext(
        calculated_hashes={"source": {"SHA-256": "b" * 64}, "target": {"SHA-256": digest}},
        declared_hashes={"source": [DeclaredHashOccurrence(
            digest, "SHA-256", "source", "manifest.txt", "native_text", declared=True,
        )]},
        display_names={"source": "manifest.txt", "target": "unrelated.bin"},
    )
    findings = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context).findings
    assert [(item.category, item.target_evidence_key) for item in findings] == [
        ("embedded_hash_match", "target")
    ]


def test_legacy_fuzzy_filename_mismatch_characterization() -> None:
    context = InvestigationContext(
        calculated_hashes={"source": {"SHA-256": "b" * 64}, "target": {"SHA-256": "c" * 64}},
        declared_hashes={"source": [DeclaredHashOccurrence(
            "a" * 64, "SHA-256", "source", "manifest.txt", "native_text",
            artifact_hint="contract", declared=True,
        )]},
        display_names={"source": "manifest.txt", "target": "contract-final.pdf"},
    )
    findings = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(context).findings
    assert [(item.category, item.target_evidence_key) for item in findings] == [
        ("declared_hash_mismatch", "target")
    ]

from __future__ import annotations

import json

import pytest

from app.correlation.case_result import (
    CASE_RESULT_SCHEMA_VERSION,
    CaseFinding,
    CaseResult,
    CaseResultJson,
    EpistemicState,
    RuleExecutionLimitation,
)
from app.enum.severity import Severity
from app.processing import ProcessingStatus


def finding(
    state: EpistemicState,
    severity: Severity = Severity.INFO,
    *,
    rule_id: str = "test_rule",
    rule_version: str = "1",
    relation_id: str | None = "relation-1",
    supports: tuple[str, ...] = ("occurrence-a", "occurrence-b"),
) -> CaseFinding:
    return CaseFinding(
        rule_id=rule_id,
        rule_version=rule_version,
        epistemic_state=state,
        severity=severity,
        relation_id=relation_id,
        supporting_occurrence_ids=supports,
        title="Resultado técnico",
        statement="Conclusão determinística limitada às evidências referenciadas.",
        metadata={"basis": "exact"},
    )


@pytest.mark.parametrize(
    ("state", "severity"),
    [
        (EpistemicState.MATCH, Severity.INFO),
        (EpistemicState.MISMATCH, Severity.INFO),
        (EpistemicState.OBSERVED, Severity.INFO),
        (EpistemicState.MISMATCH, Severity.WARNING),
        (EpistemicState.UNKNOWN, Severity.INFO),
        (EpistemicState.UNKNOWN, Severity.WARNING),
        (EpistemicState.NOT_APPLICABLE, Severity.INFO),
    ],
)
def test_epistemic_state_and_severity_are_independent(
    state: EpistemicState,
    severity: Severity,
) -> None:
    supports = () if state is EpistemicState.NOT_APPLICABLE else ("occurrence-a",)
    relation_id = None if state is EpistemicState.NOT_APPLICABLE else "relation-1"
    item = finding(state, severity, relation_id=relation_id, supports=supports)

    assert item.epistemic_state is state
    assert item.severity is severity


def test_unknown_and_not_applicable_have_distinct_semantics() -> None:
    unknown = finding(
        EpistemicState.UNKNOWN,
        relation_id=None,
        supports=("declared-hash-occurrence",),
    )
    not_applicable = finding(
        EpistemicState.NOT_APPLICABLE,
        relation_id=None,
        supports=(),
    )

    assert unknown.supporting_occurrence_ids == ("declared-hash-occurrence",)
    assert not_applicable.supporting_occurrence_ids == ()
    assert unknown.finding_id != not_applicable.finding_id


def test_operational_limitation_is_not_an_evidence_finding_or_mismatch() -> None:
    limitation = RuleExecutionLimitation(
        rule_id="ip_context",
        rule_version="1",
        code="external_lookup_unavailable",
        status=ProcessingStatus.UNAVAILABLE,
        message="A consulta externa não estava disponível.",
        metadata={"provider": "configured-provider"},
    )
    result = CaseResult(case_id="case-1", limitations=(limitation,))

    assert result.findings == ()
    assert result.limitations == (limitation,)
    assert not hasattr(limitation, "epistemic_state")
    assert limitation.status is ProcessingStatus.UNAVAILABLE


def test_finding_id_is_stable_for_reordered_and_repeated_supports() -> None:
    first = finding(
        EpistemicState.MATCH,
        supports=("occurrence-b", "occurrence-a", "occurrence-a"),
    )
    second = finding(
        EpistemicState.MATCH,
        supports=("occurrence-a", "occurrence-b"),
    )

    assert first.supporting_occurrence_ids == ("occurrence-a", "occurrence-b")
    assert first.supporting_occurrence_ids == second.supporting_occurrence_ids
    assert first.finding_id == second.finding_id


def test_additional_provenance_is_preserved_and_changes_finding_identity() -> None:
    one_support = finding(EpistemicState.MATCH, supports=("occurrence-a",))
    two_supports = finding(
        EpistemicState.MATCH,
        supports=("occurrence-a", "occurrence-b"),
    )
    result = CaseResult(case_id="case-1", findings=(two_supports, one_support))

    assert two_supports.supporting_occurrence_ids == (
        "occurrence-a",
        "occurrence-b",
    )
    assert one_support.finding_id != two_supports.finding_id
    assert {item.finding_id for item in result.findings} == {
        one_support.finding_id,
        two_supports.finding_id,
    }


def test_rule_version_is_part_of_finding_identity() -> None:
    version_one = finding(EpistemicState.MATCH, rule_version="1")
    version_two = finding(EpistemicState.MATCH, rule_version="2")

    assert version_one.rule_id == version_two.rule_id
    assert version_one.finding_id != version_two.finding_id


def test_relation_is_optional_but_deterministic_factual_claims_require_supports() -> None:
    without_relation = finding(
        EpistemicState.UNKNOWN,
        relation_id=None,
        supports=("declared-hash-occurrence",),
    )
    assert without_relation.relation_id is None

    with pytest.raises(ValueError, match="require factual supports"):
        finding(EpistemicState.MISMATCH, relation_id="relation-1", supports=())


def test_case_result_serialization_is_deterministic_and_round_trips() -> None:
    first = finding(EpistemicState.MATCH, supports=("occurrence-b", "occurrence-a"))
    second = finding(
        EpistemicState.UNKNOWN,
        rule_id="declared_hash_target",
        relation_id=None,
        supports=("declared-hash-occurrence",),
    )
    limitation = RuleExecutionLimitation(
        rule_id="ip_context",
        rule_version="1",
        code="external_lookup_unavailable",
        status=ProcessingStatus.UNAVAILABLE,
        message="A consulta externa não estava disponível.",
        metadata={"attempted": True},
    )
    left = CaseResult(
        case_id="case-1",
        findings=(second, first),
        limitations=(limitation,),
    )
    right = CaseResult(
        case_id="case-1",
        findings=(first, second),
        limitations=(limitation,),
    )

    left_payload = CaseResultJson.dumps(left, indent=None)
    right_payload = CaseResultJson.dumps(right, indent=None)
    restored = CaseResultJson.loads(left_payload)

    assert left_payload == right_payload
    assert restored == left
    assert CaseResultJson.dumps(restored, indent=None) == left_payload
    assert json.loads(left_payload)["schema_version"] == CASE_RESULT_SCHEMA_VERSION


def test_serialized_identity_tampering_is_rejected() -> None:
    result = CaseResult(case_id="case-1", findings=(finding(EpistemicState.MATCH),))
    data = json.loads(CaseResultJson.dumps(result))
    data["findings"][0]["finding_id"] = "not-the-derived-id"

    with pytest.raises(ValueError, match="does not match"):
        CaseResultJson.loads(json.dumps(data))


@pytest.mark.parametrize(
    ("scenario", "state"),
    [
        ("entity exact match", EpistemicState.MATCH),
        ("entity comparable divergence", EpistemicState.MISMATCH),
        ("declared hash exact target match", EpistemicState.MATCH),
        ("declared hash identified target differs", EpistemicState.MISMATCH),
        ("declared hash target absent", EpistemicState.UNKNOWN),
        ("artifact declares no hash", EpistemicState.NOT_APPLICABLE),
    ],
)
def test_characterized_scenarios_have_explicit_future_semantics(
    scenario: str,
    state: EpistemicState,
) -> None:
    supports = () if state is EpistemicState.NOT_APPLICABLE else (f"support:{scenario}",)
    item = finding(
        state,
        relation_id=None,
        supports=supports,
    )

    assert item.epistemic_state is state
    assert item.metadata["basis"] == "exact"


def test_success_status_cannot_masquerade_as_operational_limitation() -> None:
    with pytest.raises(ValueError, match="not an operational limitation"):
        RuleExecutionLimitation(
            rule_id="hash_rule",
            rule_version="1",
            code="not_a_limitation",
            status=ProcessingStatus.SUCCESS,
            message="A regra foi concluída.",
        )

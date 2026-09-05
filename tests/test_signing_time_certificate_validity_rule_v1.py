from __future__ import annotations

from dataclasses import replace
from itertools import permutations
from types import SimpleNamespace

from app.correlation.case_result import EpistemicState
from app.correlation.v2 import (
    CaseEvidenceIndex,
    CorrelationCandidate,
    CorrelationProvenance,
    CorrelationReport,
    EntityType,
    EvidenceGraphCorrelationEngine,
    RelationType,
    SignatureTemporalBindingCandidate,
    SignatureCorrelationProvider,
    source_file_identity,
)
from app.correlation.v2.pipeline import (
    DeterministicRuleResult,
    SigningTimeCertificateValidityRule,
)
from app.services.temporal_parser import TemporalParser


def artifact(name: str):
    return source_file_identity(display_name=name, path=f"/case/{name}")


def temporal(value: str, source, role: str, *, field: str | None = None):
    parsed = TemporalParser().parse(value)
    assert parsed is not None
    return CorrelationCandidate(
        EntityType.TIMESTAMP, parsed.raw, source,
        CorrelationProvenance(
            engine="digital_signature_engine", source_engine="pyhanko",
            source_type="pdf_embedded_signature", field=field or role,
            path=field or role, object_id="signature-field",
            raw_value=parsed.raw, timestamp_precision=parsed.precision,
            timezone_status=parsed.timezone_status,
        ), normalization_value=parsed.normalized, semantic_role=role,
    )


def binding(
    signature_id: str, certificate_id: str, source,
    signing: str, not_before: str, not_after: str,
):
    return SignatureTemporalBindingCandidate(
        signature_id, certificate_id,
        temporal(signing, source, "signer_declared_signing_time", field="signing_time"),
        temporal(not_before, source, "certificate_not_before", field="valid_from"),
        temporal(not_after, source, "certificate_not_after", field="valid_until"),
        CorrelationProvenance(
            engine="digital_signature_engine", source_engine="pyhanko",
            source_type="pdf_embedded_signature", object_id=signature_id,
        ),
    )


def evaluate(*bindings):
    candidates = [
        candidate for item in bindings
        for candidate in (item.signing_time, item.not_before, item.not_after)
    ]
    graph = EvidenceGraphCorrelationEngine().correlate(
        candidates, signature_temporal_bindings=bindings,
    )
    result = SigningTimeCertificateValidityRule().evaluate(CaseEvidenceIndex(graph))
    return graph, result


def only_finding(result: DeterministicRuleResult):
    assert not result.limitations
    assert len(result.findings) == 1
    return result.findings[0]


def test_aware_signing_time_inside_interval_is_match() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10T14:20:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    finding = only_finding(result)
    assert finding.epistemic_state is EpistemicState.MATCH
    assert finding.metadata["position"] == "inside"


def test_signing_time_before_interval_is_neutral_mismatch() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2025-12-31T23:59:59Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    finding = only_finding(result)
    assert finding.epistemic_state is EpistemicState.MISMATCH
    assert finding.severity.value == "info"
    assert finding.metadata == {**finding.metadata, "position": "before", "delta_seconds": 1.0}


def test_signing_time_after_interval_is_neutral_mismatch() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2027-01-01T00:00:01Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    finding = only_finding(result)
    assert finding.epistemic_state is EpistemicState.MISMATCH
    assert finding.metadata["position"] == "after"
    assert finding.metadata["delta_seconds"] == 1.0


def test_validity_boundaries_are_inclusive() -> None:
    for signing in ("2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"):
        _, result = evaluate(binding(
            "signature-a", "certificate-a", artifact("signed.pdf"), signing,
            "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
        ))
        assert only_finding(result).epistemic_state is EpistemicState.MATCH


def test_different_offsets_compare_by_utc_instant() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10T20:00:00-03:00",
        "2026-03-10T00:00:00Z", "2026-03-11T00:00:00Z",
    ))
    assert only_finding(result).epistemic_state is EpistemicState.MATCH


def test_naive_signing_time_is_not_compared_to_aware_interval() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10T20:00:00",
        "2026-03-10T00:00:00Z", "2026-03-11T00:00:00Z",
    ))
    assert result == DeterministicRuleResult()


def test_insufficient_precision_is_not_guessed() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10", "2026-01-01T00:00:00", "2027-01-01T00:00:00",
    ))
    assert result == DeterministicRuleResult()


def _without_relation(graph: CorrelationReport, relation_type: RelationType) -> CorrelationReport:
    return replace(
        graph,
        relations=tuple(item for item in graph.relations if item.relation_type is not relation_type),
    )


def test_missing_signing_time_or_signature_binding_does_not_mismatch() -> None:
    graph, _ = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10T12:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    rule = SigningTimeCertificateValidityRule()
    for relation_type in (
        RelationType.SIGNATURE_HAS_SIGNING_TIME,
        RelationType.SIGNATURE_USES_CERTIFICATE,
    ):
        assert rule.evaluate(CaseEvidenceIndex(_without_relation(graph, relation_type))) == DeterministicRuleResult()


def test_missing_interval_bound_does_not_mismatch() -> None:
    graph, _ = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-03-10T12:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    interval = next(
        item for item in graph.relations
        if item.relation_type is RelationType.CERTIFICATE_VALIDITY_INTERVAL
    )
    for missing in interval.object_ids:
        altered = replace(
            graph,
            relations=tuple(
                replace(item, object_ids=tuple(value for value in item.object_ids if value != missing))
                if item.stable_id == interval.stable_id else item
                for item in graph.relations
            ),
        )
        assert SigningTimeCertificateValidityRule().evaluate(CaseEvidenceIndex(altered)) == DeterministicRuleResult()


def test_two_signatures_keep_their_own_certificates_and_findings() -> None:
    source = artifact("two-signatures.pdf")
    first = binding(
        "signature-a", "certificate-a", source,
        "2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    )
    second = binding(
        "signature-b", "certificate-b", source,
        "2024-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    )
    _, result = evaluate(first, second)
    assert len(result.findings) == 2
    assert {
        (item.metadata["signature_id"], item.metadata["certificate_id"], item.epistemic_state)
        for item in result.findings
    } == {
        ("signature-a", "certificate-a", EpistemicState.MATCH),
        ("signature-b", "certificate-b", EpistemicState.MISMATCH),
    }


def test_malformed_interval_is_operational_limitation_only() -> None:
    _, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-06-01T00:00:00Z", "2027-01-01T00:00:00Z", "2026-01-01T00:00:00Z",
    ))
    assert result.findings == ()
    assert len(result.limitations) == 1
    assert result.limitations[0].code == "malformed_certificate_validity_interval"


def test_trusted_timestamp_is_distinct_and_not_substituted() -> None:
    source = artifact("signed.pdf")
    trusted = temporal(
        "2026-06-01T00:00:00Z", source, "trusted_timestamp_time", field="timestamp",
    )
    graph = EvidenceGraphCorrelationEngine().correlate([trusted])
    assert graph.entities[0].semantic_role == "trusted_timestamp_time"
    assert SigningTimeCertificateValidityRule().evaluate(CaseEvidenceIndex(graph)) == DeterministicRuleResult()


def test_finding_supports_all_occurrences_and_relation_chain() -> None:
    graph, result = evaluate(binding(
        "signature-a", "certificate-a", artifact("signed.pdf"),
        "2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
    ))
    finding = only_finding(result)
    index = CaseEvidenceIndex(graph)
    supports = index.trace_occurrences(finding.supporting_occurrence_ids)
    assert {item.semantic_role for item in supports} == {
        "signer_declared_signing_time", "certificate_not_before", "certificate_not_after",
    }
    association = index.relation(finding.relation_id or "")
    interval = index.relation(str(finding.metadata["certificate_interval_relation_id"]))
    signing = index.relation(str(finding.metadata["signing_time_relation_id"]))
    assert association and association.relation_type is RelationType.SIGNATURE_USES_CERTIFICATE
    assert interval and interval.relation_type is RelationType.CERTIFICATE_VALIDITY_INTERVAL
    assert signing and signing.relation_type is RelationType.SIGNATURE_HAS_SIGNING_TIME


def test_finding_identity_is_stable_across_binding_order() -> None:
    source = artifact("two-signatures.pdf")
    bindings = (
        binding("signature-a", "certificate-a", source, "2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
        binding("signature-b", "certificate-b", source, "2026-07-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    )
    identities = []
    for ordered in permutations(bindings):
        _, result = evaluate(*ordered)
        identities.append(tuple(item.finding_id for item in result.findings))
    assert identities[0] == identities[1]


def test_temporal_distance_does_not_change_severity() -> None:
    source = artifact("signed.pdf")
    severities = set()
    for signing in ("2025-12-31T23:59:59Z", "2000-01-01T00:00:00Z"):
        _, result = evaluate(binding(
            "signature-a", "certificate-a", source, signing,
            "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
        ))
        severities.add(only_finding(result).severity.value)
    assert severities == {"info"}


def test_signature_adapter_binds_only_supported_singleton() -> None:
    result = SimpleNamespace(digital_signature=SimpleNamespace(
        has_signature=True, signature_count=1,
        issuer="CN=Issuer", serial_number="1234",
        signing_time="2026-06-01T00:00:00Z", timestamp="2026-06-01T00:00:01Z",
        valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
    ))
    provider = SignatureCorrelationProvider()
    source = artifact("signed.pdf")
    binding_value = provider.binding(result, source)
    assert binding_value is not None
    assert binding_value.signature_id != binding_value.certificate_id
    roles = {item.semantic_role for item in provider.provide(result, source)}
    assert roles == {
        "signer_declared_signing_time", "trusted_timestamp_time",
        "certificate_not_before", "certificate_not_after",
    }


def test_aggregate_multiple_signature_result_is_not_bound() -> None:
    result = SimpleNamespace(digital_signature=SimpleNamespace(
        has_signature=True, signature_count=2,
        issuer="CN=Issuer", serial_number="1234",
        signing_time="2026-06-01T00:00:00Z", timestamp=None,
        valid_from="2026-01-01T00:00:00Z", valid_until="2027-01-01T00:00:00Z",
    ))
    assert SignatureCorrelationProvider().binding(result, artifact("signed.pdf")) is None

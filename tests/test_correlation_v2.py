from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.contracts import AnalysisContract, AnalysisState
from app.entities import EntitySource, EntitySourceType, EntityType, NormalizedEntity
from app.investigation.analysis_set import AnalysisSetArtifact, AnalysisSetCorrelator
from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.declared_hash import DeclaredHashExtractor
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.investigation.rules.embedded_hash_match_rule import EmbeddedHashMatchRule
from app.investigation.rules.embedded_hash_unmatched_rule import EmbeddedHashUnmatchedRule
from app.investigation.rules.entity_correlation_rule import EntityCorrelationRule


def entity(
    kind: EntityType, value: str, context: str, *, evidence: str,
    source: EntitySourceType = EntitySourceType.NATIVE_TEXT,
    confidence: float = 0.9,
) -> NormalizedEntity:
    return NormalizedEntity(
        kind, value, confidence, (value,),
        (EntitySource(source, evidence, page=2, start=10, end=20,
                      context_before=context, extractor="entity_resolver_v2"),),
    )


def entity_context(*items: tuple[str, str, NormalizedEntity]) -> InvestigationContext:
    context = InvestigationContext()
    for key, filename, item in items:
        context.display_names[key] = filename
        context.resolved_entities.setdefault(key, []).append(item)
    return context


def findings(context: InvestigationContext):
    return CorrelationEngine([EntityCorrelationRule()]).evaluate(context).findings


@pytest.mark.parametrize(
    ("kind", "value", "label"),
    [
        (EntityType.CPF, "52998224725", "CPF do cliente:"),
        (EntityType.PHONE, "+5521986967225", "Telefone do cliente:"),
        (EntityType.EMAIL, "a@example.com", "E-mail do cliente:"),
        (EntityType.IP, "192.0.2.10", "IP de acesso:"),
        (EntityType.MONEY, "1234.56", "Valor da parcela:"),
        (EntityType.DATETIME, "2026-08-11", "Data de assinatura:"),
    ],
)
def test_equal_comparable_entities_match(kind, value, label) -> None:
    result = findings(entity_context(
        ("a", "a.pdf", entity(kind, value, label, evidence="a")),
        ("b", "b.pdf", entity(kind, value, label, evidence="b")),
    ))
    assert [item.category for item in result] == ["entity_match"]
    assert result[0].evidence[0].page == 2


@pytest.mark.parametrize(
    ("kind", "left", "right", "label"),
    [
        (EntityType.CPF, "52998224725", "11144477735", "CPF do cliente:"),
        (EntityType.PHONE, "+5521986967225", "+5521999991111", "Telefone do cliente:"),
    ],
)
def test_different_comparable_entities_mismatch(kind, left, right, label) -> None:
    result = findings(entity_context(
        ("a", "a.pdf", entity(kind, left, label, evidence="a")),
        ("b", "b.pdf", entity(kind, right, label, evidence="b")),
    ))
    assert result[0].category == "entity_mismatch"
    assert result[0].severity == "warning"


@pytest.mark.parametrize(
    ("kind", "left_label", "right_label"),
    [
        (EntityType.CPF, "número informado", "identificador"),
        (EntityType.PHONE, "Telefone do cliente", "Telefone da empresa"),
        (EntityType.IP, "origem de rede", "destino de rede"),
        (EntityType.MONEY, "Valor da parcela", "Valor financiado"),
        (EntityType.DATETIME, "Data de assinatura", "CreationDate"),
    ],
)
def test_different_non_comparable_entities_do_not_mismatch(kind, left_label, right_label) -> None:
    result = findings(entity_context(
        ("a", "a.pdf", entity(kind, "left", left_label, evidence="a")),
        ("b", "b.pdf", entity(kind, "right", right_label, evidence="b")),
    ))
    assert result == []


def test_native_and_ocr_equal_do_not_diverge() -> None:
    value = "52998224725"
    result = findings(entity_context(
        ("a", "a.pdf", entity(EntityType.CPF, value, "CPF", evidence="a")),
        ("a", "a.pdf", entity(EntityType.CPF, value, "CPF", evidence="a", source=EntitySourceType.OCR)),
    ))
    assert not any(item.category == "source_divergence" for item in result)


def test_native_and_ocr_different_produce_source_divergence() -> None:
    result = findings(entity_context(
        ("a", "a.pdf", entity(EntityType.CPF, "52998224725", "CPF", evidence="a")),
        ("a", "a.pdf", entity(EntityType.CPF, "11144477735", "CPF", evidence="a", source=EntitySourceType.OCR)),
    ))
    assert result[0].category == "source_divergence"
    assert {item.source_type for item in result[0].evidence} == {"native_text", "ocr"}


@pytest.mark.parametrize("kind", [EntityType.AMBIGUOUS, EntityType.UNKNOWN_NUMERIC_IDENTIFIER])
def test_unresolved_entities_never_generate_strong_mismatch(kind) -> None:
    assert findings(entity_context(
        ("a", "a", entity(kind, "1", "CPF", evidence="a")),
        ("b", "b", entity(kind, "2", "CPF", evidence="b")),
    )) == []


def hash_context(source_text: str, target_hash: str | None = None) -> InvestigationContext:
    extractor = DeclaredHashExtractor()
    context = InvestigationContext(
        display_names={"a": "contrato.pdf", "b": "selfie.jpg"},
        calculated_hashes={"a": {"SHA-256": "a" * 64}, "b": {"SHA-256": target_hash or "b" * 64}},
    )
    context.declared_hashes["a"] = extractor.extract_text(
        source_text, evidence_ref="a", filename="contrato.pdf", source_type="native_text", page=8
    )
    return context


def test_declared_sha256_matches_another_artifact() -> None:
    value = "b" * 64
    result = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(hash_context(f"SHA-256: {value}", value))
    match = next(item for item in result.findings if item.category == "embedded_hash_match")
    assert match.evidence[0].page == 8
    assert match.evidence[1].extractor == "hash_engine"


def test_declared_hash_without_match_is_conservative() -> None:
    result = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(hash_context(f"SHA-256: {'c' * 64}"))
    assert result.findings[0].category == "embedded_hash_unmatched"
    assert "pode simplesmente não integrar" in result.findings[0].limitations[0]


def test_explicit_artifact_hash_mismatch() -> None:
    result = CorrelationEngine([EmbeddedHashUnmatchedRule()]).evaluate(
        hash_context(f"Hash da selfie: {'c' * 64}")
    )
    assert result.findings[0].category == "declared_hash_mismatch"
    assert result.findings[0].target_file == "selfie.jpg"


def test_equal_calculated_sha256_produces_cross_file_match() -> None:
    context = InvestigationContext(
        display_names={"a": "a.bin", "b": "b.bin"},
        calculated_hashes={"a": {"SHA-256": "d" * 64}, "b": {"SHA-256": "d" * 64}},
    )
    result = CorrelationEngine([EmbeddedHashMatchRule()]).evaluate(context)
    assert result.findings[0].category == "cross_file_match"


@pytest.mark.parametrize("source", ["native_text", "ocr"])
def test_hash_extractor_preserves_text_source(source) -> None:
    items = DeclaredHashExtractor().extract_text(
        f"SHA-256: {'e' * 64}", evidence_ref="ev", filename="doc.pdf", source_type=source, page=3
    )
    assert items[0].source_type == source
    assert items[0].page == 3


def test_hash_extractor_supports_existing_json_field() -> None:
    items = DeclaredHashExtractor().extract_json_field(
        "f" * 64, evidence_ref="ev", filename="data.json", field_path="$.selfie.sha256"
    )
    assert items[0].field_path == "$.selfie.sha256"
    assert items[0].declared is True


def test_unlabelled_hexadecimal_is_fact_only_without_warning() -> None:
    context = hash_context("Identificador " + "c" * 64)
    assert context.declared_hashes["a"][0].declared is False
    result = CorrelationEngine([EmbeddedHashMatchRule(), EmbeddedHashUnmatchedRule()]).evaluate(context)
    assert not any(item.category.startswith("embedded_hash") for item in result.findings)


def contract(name: str, evidence_id: str, sha: str, facts=(), native_text=None, ocr=None, json_data=None):
    now = datetime.now(timezone.utc)
    return AnalysisContract(
        schema_version="1.0.0", analysis_id=f"analysis-{evidence_id}", evidence_id=evidence_id,
        state=AnalysisState.COMPLETED, file={"name": name}, hashes={"sha256": sha},
        declared_type=None, detected_type=None,
        technical_structure={"json": json_data}, native_text=native_text, ocr=ocr,
        facts=list(facts), execution={"started_at": now, "finished_at": now},
    )


def test_analysis_set_one_file_and_contract_is_not_modified() -> None:
    original = contract("a.pdf", "ev-a", "a" * 64)
    before = repr(original)
    result = AnalysisSetCorrelator().correlate("set", [AnalysisSetArtifact("job", "success", contract=original)])
    assert result.state == "completed"
    assert repr(original) == before


def test_analysis_set_multiple_files() -> None:
    result = AnalysisSetCorrelator().correlate("set", [
        AnalysisSetArtifact("a", "success", contract=contract("a", "a", "a" * 64)),
        AnalysisSetArtifact("b", "success", contract=contract("b", "b", "b" * 64)),
    ])
    assert len(result.artifacts) == 2


def test_failed_member_does_not_drop_set() -> None:
    result = AnalysisSetCorrelator().correlate("set", [
        AnalysisSetArtifact("a", "success", contract=contract("a", "a", "a" * 64)),
        AnalysisSetArtifact("b", "failed", filename="bad.bin", limitation="Falha técnica."),
    ])
    assert result.state == "partial"
    assert result.limitations == ["Falha técnica."]


class BrokenRule(BaseCorrelationRule):
    rule_id = "broken"
    name = "broken"

    def evaluate(self, context):
        raise RuntimeError("internal path C:\\secret\\file")


def test_rule_exception_becomes_safe_limitation() -> None:
    result = CorrelationEngine([BrokenRule()]).evaluate(InvestigationContext())
    assert result.findings[0].category == "rule_limitation"
    assert "secret" not in result.findings[0].description


def test_finding_id_is_stable() -> None:
    context = entity_context(
        ("a", "a", entity(EntityType.CPF, "52998224725", "CPF", evidence="a")),
        ("b", "b", entity(EntityType.CPF, "52998224725", "CPF", evidence="b")),
    )
    first = findings(context)[0].finding_id
    second = findings(context)[0].finding_id
    assert first == second

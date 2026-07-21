import pytest

from app.biometric.constraint_evaluator import BiometricConstraintEvaluator
from app.engines.finding_engine import FindingsEngine
from app.models import MetadataResult
from app.models.biometric_report import (
    BiometricAlgorithmResult,
    BiometricConstraint,
    BiometricDecision,
    BiometricMetric,
    BiometricReport,
)
from app.rules.biometric_report_rule import BiometricReportRule


def _titles(report: BiometricReport) -> set[str]:
    return {
        finding.title
        for finding in BiometricReportRule().apply(report)
    }


@pytest.mark.parametrize("decision_value", ["LIVE", "PASS"])
def test_declared_decision_is_preserved_without_equivalence(
    decision_value: str,
) -> None:
    report = BiometricReport(
        decisions=[
            BiometricDecision(
                original_name="liveness",
                value=decision_value,
                source_path="$.decisions[0]",
            )
        ]
    )
    findings = BiometricReportRule().apply(report)
    decision = next(
        item
        for item in findings
        if item.title == "Decisão declarada pelo fornecedor"
    )
    assert decision.observed_value == decision_value
    assert f"'{decision_value}'" in decision.description
    assert "verificação independente" in decision.description


def test_provider_product_workflow_and_profile_present() -> None:
    report = BiometricReport(
        provider="Aware",
        product="Knomi",
        workflow="passive-liveness",
        has_profile=True,
        constraints=[BiometricConstraint("width", minimum=1)],
    )
    titles = _titles(report)
    assert {
        "Formato biométrico reconhecido",
        "Fornecedor declarado",
        "Produto declarado",
        "Workflow declarado",
        "Perfil XML encontrado",
        "Restrições de perfil encontradas",
    } <= titles


def test_profile_absent_and_no_decision_remain_factual() -> None:
    findings = BiometricReportRule().apply(BiometricReport())
    titles = {finding.title for finding in findings}
    assert "Perfil XML ausente" in titles
    assert "Decisão declarada pelo fornecedor" not in titles
    assert "Validação independente limitada" not in titles


@pytest.mark.parametrize(
    ("value", "expected_title"),
    [
        (0, "Métrica abaixo do mínimo"),
        (4, "Métrica acima do máximo"),
        ("unknown", "Avaliação de métrica não realizada"),
    ],
)
def test_outside_and_not_evaluated_metrics_generate_findings(
    value,
    expected_title: str,
) -> None:
    metric = BiometricMetric("width", value, original_unit="pixels")
    constraint = BiometricConstraint(
        "width",
        minimum=1,
        maximum=3,
        original_unit="pixels",
    )
    evaluation = BiometricConstraintEvaluator().evaluate(
        metric,
        constraint,
    )
    report = BiometricReport(
        metrics=[metric],
        constraints=[constraint],
        constraint_evaluations=[evaluation],
    )
    assert expected_title in _titles(report)


def test_within_range_does_not_generate_out_of_limit_finding() -> None:
    metric = BiometricMetric("width", 2, original_unit="pixels")
    constraint = BiometricConstraint(
        "width",
        minimum=1,
        maximum=3,
        original_unit="pixels",
    )
    report = BiometricReport(
        constraint_evaluations=[
            BiometricConstraintEvaluator().evaluate(metric, constraint)
        ]
    )
    titles = _titles(report)
    assert "Métrica abaixo do mínimo" not in titles
    assert "Métrica acima do máximo" not in titles
    assert "Avaliação de métrica não realizada" not in titles


def test_algorithm_limitations_are_explicit_and_non_conclusive() -> None:
    findings = BiometricReportRule().apply(
        BiometricReport(
            algorithms=[
                BiometricAlgorithmResult(
                    "VendorAlgorithm",
                    category="result",
                )
            ]
        )
    )
    titles = {finding.title for finding in findings}
    assert "Algoritmo proprietário não reproduzido" in titles
    assert "Validação independente limitada" in titles
    rendered = " ".join(
        f"{finding.title} {finding.description}"
        for finding in findings
    ).casefold()
    for prohibited in (
        "fraude detectada",
        "identidade confirmada",
        "selfie verdadeira",
        "pessoa viva",
        "documento autêntico",
    ):
        assert prohibited not in rendered


def test_findings_engine_keeps_old_contract_and_accepts_report() -> None:
    engine = FindingsEngine()
    assert isinstance(engine.analyze(MetadataResult()), list)
    findings = engine.analyze(
        MetadataResult(),
        biometric_report=BiometricReport(provider="Aware"),
    )
    assert any(
        finding.title == "Fornecedor declarado"
        for finding in findings
    )

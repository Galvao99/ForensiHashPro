from types import SimpleNamespace

from app.engines.finding_engine import FindingsEngine
from app.engines.score_evaluators.findings_evaluator import (
    FindingsEvaluator,
)
from app.enum.severity import Severity
from app.models import (
    Finding,
    MetadataResult,
    SignatureAnalysisStatus,
)
from app.models.integrity_result import IntegrityResult
from app.rules.integrity_rule import IntegrityRule


def _integrity(
    *,
    score: int = 0,
    signature_present: bool | None = True,
    signature_status: SignatureAnalysisStatus | None = None,
    signature_error: str | None = None,
) -> IntegrityResult:
    return IntegrityResult(
        score=score,
        technical_status=(
            "Verificações técnicas registradas individualmente; "
            "consulte os estados de cada análise."
        ),
        is_structurally_valid=True,
        hash_verified=True,
        magic_number_verified=True,
        digital_signature_present=signature_present,
        digital_signature_analysis_status=signature_status,
        digital_signature_error=signature_error,
        header_valid=True,
        eof_valid=True,
        xref_valid=True,
        trailer_valid=True,
    )


def test_residual_score_below_80_does_not_create_finding() -> None:
    findings = IntegrityRule().apply(
        _integrity(score=0)
    )

    assert findings == []


def test_info_finding_does_not_reduce_legacy_findings_score() -> None:
    info_finding = Finding(
        severity=Severity.INFO,
        category="Análise",
        title="Informação técnica",
        description="Estado técnico observado.",
    )
    result = SimpleNamespace(findings=[info_finding])

    section = FindingsEvaluator().evaluate(result)

    assert section.score == 100


def test_signature_error_is_only_an_analysis_limitation() -> None:
    integrity = _integrity(
        score=0,
        signature_present=None,
        signature_status=SignatureAnalysisStatus.ERROR,
        signature_error="parser failure",
    )

    findings = IntegrityRule().apply(integrity)
    section = FindingsEvaluator().evaluate(
        SimpleNamespace(findings=findings)
    )

    assert [finding.title for finding in findings] == [
        "Não foi possível analisar a assinatura digital"
    ]
    assert "parser failure" not in findings[0].description
    assert section.score == 100


def test_confirmed_signature_absence_remains_objective() -> None:
    findings = IntegrityRule().apply(
        _integrity(
            signature_present=False,
            signature_status=SignatureAnalysisStatus.ABSENT,
        )
    )

    assert [finding.title for finding in findings] == [
        "Assinatura digital não identificada"
    ]
    assert findings[0].observed_value == "Ausente"


def test_not_applicable_and_unsupported_remain_neutral() -> None:
    for status in (
        SignatureAnalysisStatus.NOT_APPLICABLE,
        SignatureAnalysisStatus.UNSUPPORTED,
    ):
        findings = IntegrityRule().apply(
            _integrity(
                signature_present=None,
                signature_status=status,
            )
        )

        assert findings == []


def test_info_metadata_finding_does_not_create_integrity_conclusion() -> None:
    findings = FindingsEngine().analyze(
        metadata=MetadataResult(
            raw={"EXIF:GPSLatitude": "1"}
        ),
        integrity=_integrity(score=0),
    )

    assert any(
        finding.severity == Severity.INFO
        for finding in findings
    )
    assert not any(
        finding.title
        == "Integridade técnica com pontos de atenção"
        for finding in findings
    )

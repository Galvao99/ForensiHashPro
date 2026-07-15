from pathlib import Path
from types import SimpleNamespace

from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context_builder import (
    InvestigationContextBuilder,
)
from app.investigation.rules.base_correlation_rule import (
    BaseCorrelationRule,
)
from app.models.badge import neutral_badge


def _result(path: Path, text: str, sha256: str) -> SimpleNamespace:
    return SimpleNamespace(
        file_info=SimpleNamespace(
            name=path.name,
            path=path,
        ),
        extracted_text=text,
        hashes=SimpleNamespace(sha256=sha256),
        metadata=SimpleNamespace(raw={}),
        digital_signature=None,
        timeline_events=[],
        json_analysis=None,
    )


class _IdentityRule(BaseCorrelationRule):
    rule_id = "identity_test"
    name = "Identity test"

    def evaluate(self, context):
        return [
            CorrelationFinding(
                title="Evidência identificada",
                description=f"Arquivo analisado: {evidence_key}",
                rule_id=self.rule_id,
                source_file=evidence_key,
                badges=[neutral_badge(evidence_key)],
                metadata={"arquivo": evidence_key},
            )
            for evidence_key in context.extracted_texts
        ]


def test_homonymous_files_keep_distinct_context_data(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first" / "evidence.pdf"
    second_path = tmp_path / "second" / "evidence.pdf"
    first_path.parent.mkdir()
    second_path.parent.mkdir()

    first = _result(first_path, "first text", "a" * 64)
    second = _result(second_path, "second text", "b" * 64)

    context = InvestigationContextBuilder().build([first, second])

    first_key = str(first_path.resolve())
    second_key = str(second_path.resolve())

    assert context.extracted_texts == {
        first_key: "first text",
        second_key: "second text",
    }
    assert context.calculated_hashes[first_key]["SHA-256"] == "a" * 64
    assert context.calculated_hashes[second_key]["SHA-256"] == "b" * 64
    assert context.display_names == {
        first_key: "evidence.pdf",
        second_key: "evidence.pdf",
    }


def test_correlation_keeps_identity_and_displays_only_file_name(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first" / "evidence.pdf"
    second_path = tmp_path / "second" / "evidence.pdf"
    first = _result(first_path, "first text", "a" * 64)
    second = _result(second_path, "second text", "b" * 64)
    context = InvestigationContextBuilder().build([first, second])

    result = CorrelationEngine([_IdentityRule()]).evaluate(context)

    assert len(result.findings) == 2
    assert {
        finding.source_evidence_key
        for finding in result.findings
    } == {
        str(first_path.resolve()),
        str(second_path.resolve()),
    }

    for finding in result.findings:
        assert finding.source_file == "evidence.pdf"
        assert finding.description == "Arquivo analisado: evidence.pdf"
        assert finding.badges[0].text == "evidence.pdf"
        assert finding.metadata["arquivo"] == "evidence.pdf"

from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path

import pytest

from app.application import AnalysisCoordinator, CancellationToken
from app.application import analysis_coordinator
from app.application.analysis_coordinator import AnalysisCancelledError
from app.contracts import (
    AnalysisContractJson,
    ExternalResult,
    LegacyAnalysisAdapter,
    ProgressStatus,
    SCHEMA_VERSION,
)
from app.contracts.serialization import json_safe
from app.enum.severity import Severity
from app.models import (
    AnalysisResult,
    DigitalSignatureResult,
    FileInfo,
    Finding,
    HashResult,
    MagicNumberResult,
    MetadataResult,
)
from app.models.integrity_result import IntegrityResult
from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)
from app.services.export_service import ExportService
from app.workers.analysis_worker import AnalysisWorker


UTC_NOW = datetime(2026, 8, 5, 12, 0, tzinfo=timezone.utc)


def _legacy_result() -> AnalysisResult:
    issue = ProcessingIssue(
        code="ocr_unavailable",
        status=ProcessingStatus.UNAVAILABLE,
        technical_message="Tesseract ausente.",
        user_message="OCR não executado.",
        component="ocr",
        occurred_at_utc=UTC_NOW,
        details={"api_key": "must-not-leak", "tool": "tesseract"},
        impact=ProcessingImpact.COMPONENT_ONLY,
    )
    error = ProcessingIssue(
        code="parser_failed",
        status=ProcessingStatus.FAILED,
        technical_message="Parser falhou.",
        user_message="Componente não concluído.",
        component="parser",
        occurred_at_utc=UTC_NOW,
        impact=ProcessingImpact.ANALYSIS_PARTIAL,
        original_exception=RuntimeError("private stack detail"),
    )
    return AnalysisResult(
        file_info=FileInfo("evidência.pdf", Path("C:/private/evidência.pdf"), ".pdf", 12),
        hashes=HashResult("m", "s1", "s224", "sha256", "s384", "s512"),
        metadata=MetadataResult({"PDF:Producer": "iText", "token": "secret"}),
        findings=[
            Finding(
                Severity.INFO,
                "Metadados",
                "Producer identificado",
                "Fato técnico que exige correlação.",
                recommendation="Correlacionar.",
                score=0.7,
            )
        ],
        magic_numbers=MagicNumberResult("PDF", "%PDF", True, detected_format="PDF"),
        digital_signature=DigitalSignatureResult(has_signature=False),
        integrity=IntegrityResult(None, "Dimensões separadas.", None, True, True, False),
        analysis_id="analysis-stable",
        analyzed_at=UTC_NOW,
        completed_at=UTC_NOW,
        processing_steps=[
            StepResult(
                "text_extraction",
                "ocr",
                ProcessingStatus.UNAVAILABLE,
                "OCR indisponível.",
                "OCR não executado.",
                issues=[issue],
                started_at_utc=UTC_NOW,
                finished_at_utc=UTC_NOW,
            ),
            StepResult(
                "parser",
                "parser",
                ProcessingStatus.FAILED,
                "Parser falhou.",
                "Componente não concluído.",
                issues=[error],
                started_at_utc=UTC_NOW,
                finished_at_utc=UTC_NOW,
            ),
        ],
    )


def test_contract_is_versioned_json_safe_and_deterministic() -> None:
    contract = LegacyAnalysisAdapter().convert(_legacy_result())
    first = AnalysisContractJson.dumps(contract)
    second = AnalysisContractJson.dumps(contract)
    data = json.loads(first)

    assert contract.schema_version == SCHEMA_VERSION == "1.0.0"
    assert first == second
    assert data["execution"]["started_at"].endswith("+00:00")
    assert data["file"]["name"] == "evidência.pdf"
    assert "private" not in first.lower()
    assert "must-not-leak" not in first
    assert "secret" not in first
    assert "private stack detail" not in first
    assert json_safe(Path("folder/file.bin")) == "folder\\file.bin"


def test_contract_round_trip_preserves_sections_and_external_results() -> None:
    contract = LegacyAnalysisAdapter().convert(_legacy_result())
    contract = replace(
        contract,
        external_results=[
            ExternalResult(
                "external-1",
                "IP2Location.io",
                "ip_context",
                UTC_NOW,
                {"fraud_score": 90},
                ["Geolocalização aproximada."],
            )
        ],
    )

    restored = AnalysisContractJson.loads(AnalysisContractJson.dumps(contract))

    assert AnalysisContractJson.dumps(restored) == AnalysisContractJson.dumps(contract)
    assert restored.limitations[0].code == "ocr_unavailable"
    assert restored.errors[0].code == "parser_failed"
    assert restored.findings[0].severity == "info"
    assert restored.external_results[0].provider == "IP2Location.io"


def test_contract_rejects_naive_datetime_and_non_finite_number() -> None:
    contract = LegacyAnalysisAdapter().convert(_legacy_result())

    with pytest.raises(ValueError, match="timezone"):
        AnalysisContractJson.dumps(
            replace(contract, execution={"started_at": datetime(2026, 1, 1)})
        )
    with pytest.raises(ValueError, match="não finitos"):
        AnalysisContractJson.dumps(replace(contract, metadata={"value": float("nan")}))
    payload = AnalysisContractJson.dumps(contract).replace(
        '"schema_version": "1.0.0"', '"schema_version": "2.0.0"'
    )
    with pytest.raises(ValueError, match="não suportada"):
        AnalysisContractJson.loads(payload)


def test_child_ids_are_stable_and_not_derived_from_translated_text() -> None:
    adapter = LegacyAnalysisAdapter()
    first = adapter.convert(_legacy_result())
    changed = _legacy_result()
    changed.findings[0] = replace(
        changed.findings[0],
        title="Título traduzido alterado",
        description="Texto traduzido alterado.",
    )
    second = adapter.convert(changed)

    assert first.facts[0].fact_id == second.facts[0].fact_id
    assert first.findings[0].finding_id == second.findings[0].finding_id


class _FakeService:
    def analyze(self, _path: Path, *, analysis_id: str) -> AnalysisResult:
        result = _legacy_result()
        result.analysis_id = analysis_id
        return result

    def correlate(self, _results):
        return None


def test_coordinator_runs_without_qt_and_emits_ui_independent_progress() -> None:
    events = []
    coordinator = AnalysisCoordinator(_FakeService(), progress=events.append)

    contract = coordinator.analyze(Path("evidence.pdf"))

    assert contract.analysis_id
    assert [event.status for event in events] == [
        ProgressStatus.STARTED,
        ProgressStatus.RUNNING,
        ProgressStatus.COMPLETED,
    ]
    assert all(event.analysis_id == contract.analysis_id for event in events)
    assert "PySide6" not in inspect.getsource(analysis_coordinator)


def test_coordinator_reports_pre_acquisition_cancellation() -> None:
    events = []
    token = CancellationToken(cancelled=True)
    coordinator = AnalysisCoordinator(_FakeService(), progress=events.append)

    with pytest.raises(AnalysisCancelledError):
        coordinator.analyze(Path("evidence.pdf"), cancellation=token)

    assert [event.status for event in events] == [
        ProgressStatus.STARTED,
        ProgressStatus.CANCELLED,
    ]


def test_desktop_worker_emits_legacy_and_central_contract() -> None:
    worker = AnalysisWorker(analysis_service=_FakeService(), files=[Path("evidence.pdf")])
    legacy_results = []
    contracts = []
    worker.file_analyzed.connect(legacy_results.append)
    worker.contract_analyzed.connect(contracts.append)

    worker.run()

    assert len(legacy_results) == 1
    assert len(contracts) == 1
    assert contracts[0].analysis_id == legacy_results[0].analysis_id


def test_export_service_writes_utf8_versioned_contract(tmp_path: Path) -> None:
    output = tmp_path / "análise.json"
    contract = LegacyAnalysisAdapter().convert(_legacy_result())

    ExportService().export_analysis_json(contract, output)

    assert output.read_bytes().decode("utf-8").endswith("\n")
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "1.0.0"

from dataclasses import replace
from datetime import datetime, timezone
import inspect
import json
from pathlib import Path, PurePosixPath, PureWindowsPath

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
from app.services.timeline_service import TimelineService
from app.workers.analysis_worker import AnalysisWorker
from app.entities import EntitySource, EntitySourceType, EntityType, NormalizedEntity
from app.investigation.correlation_result import CorrelationResult


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
    assert json_safe(Path("folder/file.bin")) == "folder/file.bin"
    assert json_safe(PurePosixPath("folder/file.bin")) == "folder/file.bin"
    assert json_safe(PureWindowsPath("folder/file.bin")) == "folder/file.bin"


def test_resolved_entity_is_exposed_as_traceable_fact_without_internal_path() -> None:
    result = _legacy_result()
    result.resolved_entities = [
        NormalizedEntity(
            entity_type=EntityType.PHONE,
            normalized_value="+5521986967225",
            confidence=0.9,
            raw_values=("(21) 98696-7225",),
            sources=(
                EntitySource(
                    source_type=EntitySourceType.NATIVE_TEXT,
                    source_file="C:/private/evidência.pdf",
                    page=4,
                    start=12,
                    end=28,
                    context_before="Telefone: ",
                    extractor="entity_resolver_v2",
                ),
            ),
        )
    ]

    contract = LegacyAnalysisAdapter().convert(result)
    entity_fact = next(fact for fact in contract.facts if fact.kind == "entity")
    serialized = AnalysisContractJson.dumps(contract)

    assert entity_fact.data["type"] == "phone"
    assert entity_fact.data["provenance"][0]["page"] == 4
    assert entity_fact.data["provenance"][0]["evidence_ref"] == contract.evidence_id
    assert "C:/private" not in serialized


def test_signature_collection_only_contains_an_identified_signature() -> None:
    result = _legacy_result()
    assert LegacyAnalysisAdapter().convert(result).signatures == []


def test_metadata_dates_reach_serialized_analysis_contract_timeline() -> None:
    result = _legacy_result()
    result.metadata = MetadataResult({
        "PDF:CreateDate": "2023-08-16T14:30:00",
        "PDF:ModifyDate": "2025-02-14T09:17:00",
    })
    timeline = TimelineService().build(result)
    result.timeline_events = timeline.events
    result.timeline_warnings = timeline.warnings
    result.timeline_limitations = timeline.limitations

    contract = LegacyAnalysisAdapter().convert(result)
    payload = json.loads(AnalysisContractJson.dumps(contract))
    artifact_events = [
        item for item in payload["timeline"]
        if item.get("category") == "metadata"
    ]

    assert [item["title"] for item in artifact_events] == ["CreateDate", "ModifyDate"]
    assert [item["timestamp"] for item in artifact_events] == [
        "2023-08-16T14:30:00", "2025-02-14T09:17:00"
    ]


def test_timeline_limitations_reach_contract_without_events() -> None:
    result = _legacy_result()
    result.timeline_events = []
    result.timeline_warnings = []
    result.timeline_limitations = [
        "A fonte temporal não forneceu eventos normalizáveis."
    ]

    contract = LegacyAnalysisAdapter().convert(result)

    assert contract.timeline == [
        {
            "record_type": "limitation",
            "message": "A fonte temporal não forneceu eventos normalizáveis.",
        }
    ]


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


class _FakeCaseService(_FakeService):
    def __init__(self) -> None:
        self.analyzed_paths: list[Path] = []
        self.correlation_sizes: list[int] = []

    def analyze(self, path: Path, *, analysis_id: str) -> AnalysisResult:
        self.analyzed_paths.append(path)
        value = super().analyze(path, analysis_id=analysis_id)
        stat = path.stat()
        value.file_info = replace(
            value.file_info,
            name=path.name,
            path=path,
            size_bytes=stat.st_size,
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        )
        return value

    def correlate_case(self, _case_id: str, results) -> CorrelationResult:
        self.correlation_sizes.append(len(results))
        return CorrelationResult()


def test_folder_batch_schedules_all_files_without_selection(tmp_path: Path) -> None:
    paths = [tmp_path / f"evidence-{index}.bin" for index in range(10)]
    for path in paths:
        path.write_bytes(b"evidence")
    service = _FakeCaseService()
    worker = AnalysisWorker(
        analysis_service=service, files=paths, case_id="case-1"
    )
    emitted = []
    worker.file_analyzed.connect(emitted.append)

    worker.run()

    assert service.analyzed_paths == paths
    assert len(emitted) == 10
    assert service.correlation_sizes == list(range(0, 11))


def test_folder_batch_reuses_valid_results_and_reports_progress(tmp_path: Path) -> None:
    cached_path = tmp_path / "cached.bin"
    pending_path = tmp_path / "pending.bin"
    cached_path.write_bytes(b"cached")
    pending_path.write_bytes(b"pending")
    service = _FakeCaseService()
    cached = service.analyze(cached_path, analysis_id="cached-analysis")
    service.analyzed_paths.clear()
    worker = AnalysisWorker(
        analysis_service=service,
        files=[cached_path, pending_path],
        case_id="case-1",
        cached_results={str(cached_path.resolve()): cached},
    )
    progress = []
    worker.case_progress_changed.connect(progress.append)

    worker.run()

    assert service.analyzed_paths == [pending_path]
    assert progress[-1] == {
        "total": 2,
        "analyzed": 2,
        "failed": 0,
        "pending": 0,
        "current_file": "",
    }


def test_folder_batch_progress_counts_failures(tmp_path: Path) -> None:
    good = tmp_path / "good.bin"
    bad = tmp_path / "bad.bin"
    good.write_bytes(b"good")
    bad.write_bytes(b"bad")

    class FailingService(_FakeCaseService):
        def analyze(self, path: Path, *, analysis_id: str) -> AnalysisResult:
            if path == bad:
                raise RuntimeError("technical failure")
            return super().analyze(path, analysis_id=analysis_id)

    worker = AnalysisWorker(
        analysis_service=FailingService(), files=[good, bad], case_id="case-1"
    )
    progress = []
    states = []
    worker.case_progress_changed.connect(progress.append)
    worker.file_state_changed.connect(lambda path, state: states.append((path, state)))

    worker.run()

    assert progress[-1]["total"] == 2
    assert progress[-1]["analyzed"] == 1
    assert progress[-1]["pending"] == 0
    assert progress[-1]["failed"] == 1
    assert states[-1] == (str(bad.resolve()), "failed")


def test_export_service_writes_utf8_versioned_contract(tmp_path: Path) -> None:
    output = tmp_path / "análise.json"
    contract = LegacyAnalysisAdapter().convert(_legacy_result())

    ExportService().export_analysis_json(contract, output)

    assert output.read_bytes().decode("utf-8").endswith("\n")
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "1.0.0"

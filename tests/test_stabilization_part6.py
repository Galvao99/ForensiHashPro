from __future__ import annotations

import builtins
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.biometric.parsers import AwareKnomiReportParser, BiometricParserRegistry
from app.contracts import LegacyAnalysisAdapter
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer, UnacquiredEvidenceError
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.integrations.ip.ip_exceptions import IpProviderError, IpTimeoutError
from app.integrations.ip.ip_models import IpLookupResult
from app.integrations.ip.ip_service import IpAnalysisService
from app.models import AnalysisResult
from app.pages.comparison_workspace import ComparisonWorkspace
from app.processing import ProcessingStatus
from app.services.biometric_report_service import BiometricReportService
from app.services.json_parser_service import JsonParserService
from app.settings import AppSettings

from tests.test_analysis_contract import _legacy_result


BIOMETRIC_FIXTURE = Path("tests/fixtures/biometrics/aware_knomi_report.json")


def _analyzer(*, biometric_service=None, json_service=None) -> FileAnalyzer:
    return FileAnalyzer(
        hash_engine=HashEngine(),
        metadata_engine=MetadataEngine(),
        findings_engine=FindingsEngine(),
        magic_number_engine=MagicNumberEngine(),
        digital_signature_engine=DigitalSignatureEngine(),
        pdf_structure_engine=PDFStructureEngine(),
        biometric_report_service=biometric_service,
        json_parser_service=json_service,
    )


def _step(result: AnalysisResult, code: str):
    return next(item for item in result.processing_steps if item.code == code)


def test_individual_contract_distinguishes_unexecuted_sections_from_empty_results() -> None:
    contract = LegacyAnalysisAdapter().convert(_legacy_result())

    assert contract.ip_addresses is None
    assert contract.timeline is None
    assert contract.comparison is None
    assert contract.external_results is None
    steps = {item["code"]: item for item in contract.processing_steps}
    assert steps["ip_context"]["status"] == ProcessingStatus.SKIPPED.value
    assert steps["comparison"]["safe_details"]["reason"] == "different_scope"
    assert steps["timeline"]["safe_details"]["reason"] == "not_executed"


def test_correlation_is_not_embedded_in_individual_contract() -> None:
    contract = LegacyAnalysisAdapter().convert(_legacy_result())

    assert not hasattr(contract, "correlation")
    assert contract.comparison is None
    assert contract.execution["runtime"] == "python"


def test_file_analyzer_rejects_unacquired_public_path_and_keeps_fixture_entry(
    tmp_path: Path,
) -> None:
    path = tmp_path / "fixture.txt"
    path.write_text("controlled fixture", encoding="utf-8")
    analyzer = _analyzer()

    with pytest.raises(UnacquiredEvidenceError, match="AnalysisService"):
        analyzer.analyze(path)

    assert analyzer.analyze_fixture(path).hashes.sha256


def test_comparison_workspace_enters_through_analysis_service(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = tmp_path / "left.bin"
    selected.write_bytes(b"controlled")

    class Service:
        def __init__(self) -> None:
            self.paths: list[Path] = []

        def analyze(self, path: Path):
            self.paths.append(path)
            return SimpleNamespace(file_info=SimpleNamespace(name=path.name))

    service = Service()
    workspace = SimpleNamespace(
        analysis_service=service,
        left_result=None,
        left_label=SimpleNamespace(setText=lambda _text: None),
        try_compare=lambda: None,
    )
    monkeypatch.setattr(
        "app.pages.comparison_workspace.QFileDialog.getOpenFileName",
        lambda *_args: (str(selected), ""),
    )

    ComparisonWorkspace.select_left_file(workspace)

    assert service.paths == [selected]


def test_biometric_processing_states_are_distinct(tmp_path: Path) -> None:
    service = BiometricReportService(
        BiometricParserRegistry([AwareKnomiReportParser()])
    )
    analyzer = _analyzer(biometric_service=service)
    non_json = tmp_path / "sample.txt"
    non_json.write_text("not biometric", encoding="utf-8")
    invalid = tmp_path / "invalid.json"
    invalid.write_text("{", encoding="utf-8")
    ordinary = tmp_path / "ordinary.json"
    ordinary.write_text('{"ordinary": true}', encoding="utf-8")

    assert _step(analyzer.analyze_fixture(non_json), "biometric_analysis").status is ProcessingStatus.SKIPPED
    assert _step(analyzer.analyze_fixture(invalid), "biometric_analysis").status is ProcessingStatus.FAILED
    assert _step(analyzer.analyze_fixture(ordinary), "biometric_analysis").status is ProcessingStatus.NO_FINDINGS
    success = _step(analyzer.analyze_fixture(BIOMETRIC_FIXTURE), "biometric_analysis")
    assert success.status is ProcessingStatus.SUCCESS
    assert success.value is not None


def test_biometric_parser_failure_is_not_reported_as_absence(tmp_path: Path) -> None:
    class FailingService:
        def parse(self, _path: Path):
            from app.services.biometric_report_exceptions import BiometricReportParsingError

            raise BiometricReportParsingError("internal parser detail")

    path = tmp_path / "report.json"
    path.write_text("{}", encoding="utf-8")
    step = _step(
        _analyzer(biometric_service=FailingService()).analyze_fixture(path),
        "biometric_analysis",
    )

    assert step.status is ProcessingStatus.FAILED
    assert step.issues[0].code == "biometric_parser_failed"
    assert "internal parser detail" not in step.user_message


def test_json_processing_invalid_unrecognized_unavailable_and_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "report.json"
    path.write_text("{}", encoding="utf-8")
    service = JsonParserService()

    original_import = builtins.__import__

    def missing_rust(name, *args, **kwargs):
        if name == "forensihash_core":
            raise ImportError("missing")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing_rust)
    assert service.parse_step(path).status is ProcessingStatus.UNAVAILABLE
    monkeypatch.setattr(builtins, "__import__", original_import)

    invalid_core = SimpleNamespace(
        parse_json_file=lambda *_args: json.dumps({"is_valid": False})
    )
    monkeypatch.setitem(__import__("sys").modules, "forensihash_core", invalid_core)
    assert service.parse_step(path).status is ProcessingStatus.FAILED

    empty_core = SimpleNamespace(
        parse_json_file=lambda *_args: json.dumps({"is_valid": True, "fields": []})
    )
    monkeypatch.setitem(__import__("sys").modules, "forensihash_core", empty_core)
    assert service.parse_step(path).status is ProcessingStatus.NO_FINDINGS

    success_core = SimpleNamespace(
        parse_json_file=lambda *_args: json.dumps(
            {
                "is_valid": True,
                "fields": [
                    {"path": "$.a", "key": "a", "value": 1, "value_type": "number"}
                ],
            }
        )
    )
    monkeypatch.setitem(__import__("sys").modules, "forensihash_core", success_core)
    assert service.parse_step(path).status is ProcessingStatus.SUCCESS


class _Settings:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def load(self) -> AppSettings:
        return self.settings


class _Client:
    def __init__(self, result=None, error: BaseException | None = None) -> None:
        self.result = result
        self.error = error

    def lookup(self, _ip: str):
        if self.error:
            raise self.error
        return self.result


@pytest.mark.parametrize(
    ("settings", "client", "status", "code"),
    [
        (AppSettings(), None, ProcessingStatus.UNAVAILABLE, "ip_integration_disabled"),
        (
            AppSettings(ip_lookup_enabled=True),
            None,
            ProcessingStatus.UNAVAILABLE,
            "ip_key_missing",
        ),
        (
            AppSettings(ip_api_key="placeholder", ip_lookup_enabled=True),
            _Client(error=IpTimeoutError()),
            ProcessingStatus.FAILED,
            "ip_timeout",
        ),
        (
            AppSettings(ip_api_key="placeholder", ip_lookup_enabled=True),
            _Client(error=IpProviderError()),
            ProcessingStatus.FAILED,
            "ip_provider_error",
        ),
        (
            AppSettings(ip_api_key="placeholder", ip_lookup_enabled=True),
            _Client(result=IpLookupResult("8.8.8.8", lookup_performed=True)),
            ProcessingStatus.SUCCESS,
            None,
        ),
    ],
)
def test_ip_processing_states(
    settings: AppSettings,
    client: _Client | None,
    status: ProcessingStatus,
    code: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if client is not None:
        monkeypatch.setattr(
            "app.integrations.ip.ip_provider.IpProvider.get_client",
            lambda _provider: client,
        )
    service = IpAnalysisService(_Settings(settings))

    step = service.analyze_step("8.8.8.8")

    assert step.status is status
    if code is not None:
        assert step.issues[0].code == code
        assert step.value is not None and step.value.lookup_performed is False
    else:
        assert step.issues == []
        assert step.value is not None and step.value.lookup_performed is True

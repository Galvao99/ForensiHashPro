from pathlib import Path

from app.biometric.parsers import AwareKnomiReportParser, BiometricParserRegistry
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.factory.application_factory import ApplicationFactory
from app.models.analysis_result import AnalysisResult
from app.services.biometric_report_service import BiometricReportService


def _analyzer(service) -> FileAnalyzer:
    return FileAnalyzer(
        hash_engine=HashEngine(),
        metadata_engine=MetadataEngine(),
        findings_engine=FindingsEngine(),
        magic_number_engine=MagicNumberEngine(),
        digital_signature_engine=DigitalSignatureEngine(),
        pdf_structure_engine=PDFStructureEngine(),
        biometric_report_service=service,
    )


def test_analysis_result_default_and_factory_registration() -> None:
    assert AnalysisResult.__dataclass_fields__["biometric_report"].default is None
    service = ApplicationFactory.create_analysis_service()
    assert service.analyzer.biometric_report_service is not None


def test_file_analyzer_adds_biometric_report_and_keeps_json_analysis() -> None:
    service = BiometricReportService(
        BiometricParserRegistry([AwareKnomiReportParser()])
    )
    result = _analyzer(service).analyze(
        Path("tests/fixtures/biometrics/aware_knomi_report.json")
    )
    assert result.biometric_report is not None
    assert result.biometric_report.provider == "Aware"
    assert result.json_analysis is not None
    assert any(
        finding.title == "Decisão declarada pelo fornecedor"
        for finding in result.findings
    )


def test_common_json_remains_non_biometric(tmp_path: Path) -> None:
    path = tmp_path / "common.json"
    path.write_text('{"ordinary": true}', encoding="utf-8")
    service = BiometricReportService(
        BiometricParserRegistry([AwareKnomiReportParser()])
    )
    result = _analyzer(service).analyze(path)
    assert result.biometric_report is None
    assert result.json_analysis is not None

import json
from pathlib import Path

import pytest

from app.biometric.parsers import AwareKnomiReportParser, BiometricParserRegistry
from app.models.biometric_report import ConstraintEvaluationStatus
from app.services.biometric_report_exceptions import (
    AmbiguousBiometricReportError,
    BiometricReportParsingError,
    InvalidBiometricJsonError,
    UnsupportedBiometricExtensionError,
    UnrecognizedBiometricReportError,
)
from app.services.biometric_report_service import BiometricReportService


FIXTURE = Path("tests/fixtures/biometrics/aware_knomi_report.json")


def _service(*parsers) -> BiometricReportService:
    return BiometricReportService(BiometricParserRegistry(list(parsers) or [AwareKnomiReportParser()]))


def test_aware_fixture_detection_and_complete_extraction() -> None:
    report = _service().parse(FIXTURE)
    assert (report.provider, report.product, report.version, report.workflow) == (
        "Aware", "Knomi", "1.0", "passive-liveness"
    )
    assert report.analysis_date is not None
    assert "completedAt" in report.timestamps
    assert report.warnings
    assert report.decisions[0].value == "LIVE"
    assert report.algorithms[0].original_name == "VendorLiveness"
    assert report.metrics[0].canonical_name == "image.width_pixels"
    assert report.metrics[-1].canonical_name is None
    assert report.metrics[-1].original_name == "vendorSpecificMetric"
    assert report.evidences[0].original_reference == "frames/face-001.jpg"
    assert report.evidences[0].resolved_path is None
    assert report.has_profile is True
    assert len(report.constraints) == 2
    assert report.constraint_evaluations[0].status is ConstraintEvaluationStatus.PREFERRED


def test_payload_object_is_preserved_without_deep_copy() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    parser = AwareKnomiReportParser()
    report = parser.parse(payload)
    assert report.raw_payload is payload


def test_common_json_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "common.json"
    path.write_text('{"score": 1, "face": true}', encoding="utf-8")
    with pytest.raises(UnrecognizedBiometricReportError):
        _service().parse(path)


@pytest.mark.parametrize("content", ["{", "[]"])
def test_invalid_json_or_root(tmp_path: Path, content: str) -> None:
    path = tmp_path / "invalid.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(InvalidBiometricJsonError):
        _service().parse(path)


def test_extension_missing_file_utf8_and_utf8_sig(tmp_path: Path) -> None:
    with pytest.raises(BiometricReportParsingError):
        _service().parse(tmp_path / "missing.json")
    text = FIXTURE.read_text(encoding="utf-8")
    bad_extension = tmp_path / "report.txt"
    bad_extension.write_text(text, encoding="utf-8")
    with pytest.raises(UnsupportedBiometricExtensionError):
        _service().parse(bad_extension)
    for encoding in ("utf-8", "utf-8-sig"):
        path = tmp_path / f"report-{encoding}.json"
        path.write_text(text, encoding=encoding)
        assert _service().parse(path).provider == "Aware"


def test_ambiguous_detection() -> None:
    parser = AwareKnomiReportParser()
    with pytest.raises(AmbiguousBiometricReportError):
        _service(parser, parser).parse(FIXTURE)


def test_optional_fields_lists_and_profile_absence(tmp_path: Path) -> None:
    payload = {
        "transaction": {"provider": "Aware", "product": "Knomi"},
        "decisions": [], "algorithms": [], "metrics": {}, "evidence": []
    }
    path = tmp_path / "minimal.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = _service().parse(path)
    assert report.version is None
    assert report.decisions == report.algorithms == report.metrics == []
    assert report.has_profile is False


def test_algorithm_metrics_are_evaluated_against_profile(tmp_path: Path) -> None:
    payload = {
        "transaction": {"provider": "Aware", "product": "Knomi"},
        "algorithms": [
            {
                "name": "VendorAlgorithm",
                "metrics": {
                    "yaw": {"value": 20, "unit": "degrees"}
                },
            }
        ],
        "profileXml": (
            '<profile><metric name="yaw" min="-10" max="10" '
            'unit="degrees"/></profile>'
        ),
    }
    path = tmp_path / "algorithm-metric.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = _service().parse(path)
    assert report.metrics[0].source_path == "$.algorithms[0].metrics.yaw"
    assert (
        report.constraint_evaluations[0].status
        is ConstraintEvaluationStatus.ABOVE_MAXIMUM
    )

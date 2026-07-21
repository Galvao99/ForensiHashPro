import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from app.biometric.parsers import AwareKnomiReportParser, BiometricParserRegistry
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
    registered = list(parsers) or [AwareKnomiReportParser()]
    return BiometricReportService(BiometricParserRegistry(registered))


def _payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_real_structure_is_recognized_and_payload_preserved() -> None:
    payload = _payload()
    parser = AwareKnomiReportParser()
    assert parser.recognizes(payload) is True
    report = parser.parse(payload)
    assert report.raw_payload is payload


def test_similar_json_is_rejected(tmp_path: Path) -> None:
    payload = _payload()
    payload["task"] = "other_task"
    payload["server"] = "other_server"
    path = tmp_path / "similar.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
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
    wrong = tmp_path / "report.txt"
    wrong.write_text(text, encoding="utf-8")
    with pytest.raises(UnsupportedBiometricExtensionError):
        _service().parse(wrong)
    for encoding in ("utf-8", "utf-8-sig"):
        path = tmp_path / f"report-{encoding}.json"
        path.write_text(text, encoding=encoding)
        assert _service().parse(path).provider == "Aware"


def test_ambiguous_detection() -> None:
    parser = AwareKnomiReportParser()
    with pytest.raises(AmbiguousBiometricReportError):
        _service(parser, parser).parse(FIXTURE)


class _NeverParser(AwareKnomiReportParser):
    def recognizes(self, payload: Mapping) -> bool:
        return False


def test_second_parser_does_not_change_core_selection() -> None:
    report = _service(_NeverParser(), AwareKnomiReportParser()).parse(FIXTURE)
    assert report.provider == "Aware"


def test_real_structure_with_optional_fields_absent(tmp_path: Path) -> None:
    payload = _payload()
    payload.pop("video_version")
    workflow = payload["input"]["workflow_data"]
    workflow.pop("profile")
    workflow["frames"] = []
    payload["result"]["algorithm_results"] = []
    payload["result"]["liveness_result"] = {}
    path = tmp_path / "partial.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    report = _service().parse(path)
    assert report.provider == "Aware"
    assert report.decisions == []
    assert report.has_profile is False
    assert report.metadata["video_version_raw"] is None

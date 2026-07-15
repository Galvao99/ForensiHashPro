from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from app.investigation.investigation_context_builder import InvestigationContextBuilder


def _result(path: Path, text: str = "", **values):
    base = dict(
        file_info=SimpleNamespace(name=path.name, path=path),
        extracted_text=text,
        hashes=SimpleNamespace(sha256="a" * 64),
        metadata=SimpleNamespace(raw={"Producer": "PDF Tool", "CreateDate": "2026-07-16"}),
        digital_signature=SimpleNamespace(status="valid"),
        timeline_events=[SimpleNamespace(title="Evento")],
        detected_ips=["192.0.2.1"],
        ip_results=[SimpleNamespace(ip="192.0.2.1")],
        json_analysis=SimpleNamespace(is_valid=True),
    )
    base.update(values)
    return SimpleNamespace(**base)


def test_structured_date_has_priority_over_ocr(tmp_path: Path):
    class FailingExtractor:
        def extract(self, text: str):
            raise AssertionError("OCR não deve ser consultado com data estruturada válida")

    result = _result(
        tmp_path / "evidence.pdf",
        "Data da contratação: 15/07/2026",
        contract_date="2025-01-02T03:04:05+00:00",
    )
    context = InvestigationContextBuilder(
        contract_date_extractor=FailingExtractor(),  # type: ignore[arg-type]
    ).build([result])
    key = str(result.file_info.path.resolve())
    assert context.contract_dates[key] == datetime.fromisoformat("2025-01-02T03:04:05+00:00")


def test_ocr_fallback_populates_correct_evidence_key_and_preserves_context(tmp_path: Path):
    result = _result(tmp_path / "evidence.pdf", "Data da contratação: 15 de julho de 2026")
    context = InvestigationContextBuilder().build([result])
    key = str(result.file_info.path.resolve())

    assert context.contract_dates[key] == datetime(2026, 7, 15)
    assert context.extracted_texts[key]
    assert context.calculated_hashes[key]["SHA-256"] == "a" * 64
    assert context.metadata_values[key]["Producer"] == "PDF Tool"
    assert context.metadata_dates[key]["CreateDate"] == datetime(2026, 7, 16)
    assert context.producers[key] == "PDF Tool"
    assert context.signature_results[key] is result.digital_signature
    assert context.timeline_events[key] == result.timeline_events
    assert context.detected_ips[key] == ["192.0.2.1"]
    assert context.ip_results[key] == result.ip_results
    assert context.json_results[key] is result.json_analysis


def test_missing_or_invalid_free_text_does_not_populate_contract_date(tmp_path: Path):
    results = [
        _result(tmp_path / "empty.pdf"),
        _result(tmp_path / "invalid.pdf", "Data da contratação: 31/02/2026"),
        _result(tmp_path / "weak.pdf", "Referência: 15/07/2026"),
    ]
    context = InvestigationContextBuilder().build(results)
    assert context.contract_dates == {}


def test_homonymous_paths_get_distinct_contract_date_keys(tmp_path: Path):
    first = _result(tmp_path / "a" / "same.pdf", "Assinado em 15/07/2026")
    second = _result(tmp_path / "b" / "same.pdf", "Firmado em 16/07/2026")
    context = InvestigationContextBuilder().build([first, second])
    assert context.contract_dates == {
        str(first.file_info.path.resolve()): datetime(2026, 7, 15),
        str(second.file_info.path.resolve()): datetime(2026, 7, 16),
    }

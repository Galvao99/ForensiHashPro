from __future__ import annotations

from pathlib import Path

from app.contracts import AnalysisContract, AnalysisState, Fact, FindingContract, Limitation
from web.backend.app.presentation import AnalysisPresenter


def _contract() -> AnalysisContract:
    return AnalysisContract(
        schema_version="1.0.0",
        analysis_id="analysis-public",
        evidence_id="evidence-public",
        state=AnalysisState.PARTIAL,
        file={
            "name": "document.pdf",
            "size_bytes": 123,
            "modified_at": "2026-08-08T00:00:00+00:00",
        },
        hashes={"sha256": "abc", "md5": "def"},
        declared_type=".pdf",
        detected_type="PDF",
        metadata={
            "PDF:Producer": "Synthetic Producer",
            "EXIF:GPSLatitude": -23.5,
            "File:Directory": "/tmp/forensihash/evidence/private",
            "File:FileModifyDate": "2026:08:08 00:00:00+00:00",
            "SourceFile": "C:\\Users\\person\\private.pdf",
            "APIKey": "must-not-leak",
        },
        technical_structure={
            "pdf": {"pdf_version": "1.7", "object_count": 4},
            "binary": {
                "header_bytes": b"private",
                "strings": [{"value": "technical string"}],
            },
            "json": {
                "fields": [
                    {"key": "password", "value": "must-not-leak"},
                    {"key": "document", "value": "synthetic"},
                ]
            },
        },
        facts=[
            Fact("fact-1", "metadata", "metadata_engine", {"Producer": "Synthetic"})
        ],
        findings=[
            FindingContract(
                "finding-1", "rule.synthetic", "info", "Achado", "Fato técnico"
            )
        ],
        limitations=[
            Limitation("limitation-1", "tool_unavailable", "ocr", "OCR indisponível", "component_only")
        ],
        processing_steps=[
            {
                "code": "metadata_extraction",
                "status": "success",
                "technical_message": "Concluído.",
                "safe_details": {"working_path": Path("/tmp/private")},
            }
        ],
    )


def _walk(value: object):
    yield value
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from _walk(item)


def test_presenter_preserves_forensic_sections_and_processing_states() -> None:
    payload = AnalysisPresenter().present(_contract())

    assert payload["hashes"] == {"md5": "def", "sha256": "abc"}
    assert payload["metadata"]["PDF:Producer"] == "Synthetic Producer"
    assert payload["metadata"]["EXIF:GPSLatitude"] == -23.5
    assert payload["technical_structure"]["pdf"]["object_count"] == 4
    assert payload["facts"][0]["kind"] == "metadata"
    assert payload["findings"][0]["rule_id"] == "rule.synthetic"
    assert payload["limitations"][0]["code"] == "tool_unavailable"
    assert payload["processing_steps"][0]["status"] == "success"


def test_presenter_recursively_removes_internal_and_sensitive_data() -> None:
    payload = AnalysisPresenter().present(_contract())
    values = [str(value).lower() for value in _walk(payload)]
    joined = " ".join(values)

    assert "original_path" not in joined
    assert "working_path" not in joined
    assert "workspace" not in joined
    assert "/tmp/" not in joined
    assert "c:\\users" not in joined
    assert "must-not-leak" not in joined
    assert "header_bytes" not in joined
    assert "filemodifydate" not in joined
    assert "modified_at" not in joined
    assert "traceback" not in joined
    assert payload["technical_structure"]["json"]["fields"][0]["value"] == "[redacted]"

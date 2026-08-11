from __future__ import annotations

from app.contracts import AnalysisContract, AnalysisState
from web.backend.app.presentation import AnalysisPresenter


def _contract(timeline):
    return AnalysisContract(
        schema_version="1.0.0", analysis_id="analysis-1", evidence_id="evidence-1",
        state=AnalysisState.COMPLETED,
        file={"name": "C:\\internal\\staging\\secret.pdf"}, hashes={"sha256": "a" * 64},
        declared_type="pdf", detected_type="pdf", timeline=timeline,
    )


def test_public_timeline_preserves_public_filename_and_removes_internal_path():
    contract = _contract([{
        "record_type": "event", "event_id": "event-1", "title": "CreationDate",
        "timestamp": "2023-01-01", "temporal_status": "date_only",
        "filename": "C:\\internal\\staging\\secret.pdf", "source_type": "metadata",
    }])
    payload = AnalysisPresenter().present(contract, display_name="contrato.pdf")
    assert payload["timeline"][0]["filename"] == "contrato.pdf"
    assert "C:\\internal" not in str(payload)


def test_analysis_contract_version_is_unchanged_with_timeline_v2():
    payload = AnalysisPresenter().present(_contract([]), display_name="contrato.pdf")
    assert payload["schema_version"] == "1.0.0"


def test_archive_entries_serialize_with_public_names_without_server_paths():
    contract = _contract([])
    archive = {
        "parser_id": "archive_zip_v1",
        "embedded_artifacts": [{
            "embedded_artifact_ref": "entry-1", "filename": "setup.exe",
            "internal_path": "folder/setup.exe", "inspection_flags": ["executable_content_detected"],
            "server_path": "C:\\internal\\archive\\setup.exe",
        }],
    }
    object.__setattr__(contract, "technical_structure", {"archive": archive})
    payload = AnalysisPresenter().present(contract, display_name="evidencias.zip")
    entry = payload["technical_structure"]["archive"]["embedded_artifacts"][0]
    assert entry["filename"] == "setup.exe"
    assert entry["internal_path"] == "folder/setup.exe"
    assert "server_path" not in entry
    assert "C:\\internal" not in str(payload)

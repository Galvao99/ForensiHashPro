from __future__ import annotations

from hashlib import sha256
from pathlib import Path

import fitz
import pytest
from PIL import Image

from app.evidence import EvidenceManager
from app.factory.application_factory import ApplicationFactory
from app.services.analysis_service import AnalysisService
from web.backend.app.services import WebAnalysisService


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("kind", ["image", "pdf", "json"])
def test_official_analysis_preserves_input_for_specialized_flows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    monkeypatch.setenv("FORENSIHASH_TEMP_DIR", str(tmp_path / "runtime"))
    if kind == "image":
        evidence = tmp_path / "synthetic.png"
        Image.new("RGB", (40, 40), "white").save(evidence)
    elif kind == "pdf":
        evidence = tmp_path / "synthetic.pdf"
        document = fitz.open()
        document.new_page().insert_text((72, 72), "ForensiHash")
        document.save(evidence)
        document.close()
    else:
        evidence = tmp_path / "synthetic.json"
        evidence.write_text('{"document": "synthetic"}', encoding="utf-8")

    before = _digest(evidence)
    contract = WebAnalysisService().analyze(evidence, staging_sha256=before)

    assert _digest(evidence) == before
    assert contract.hashes["sha256"] == before
    if kind == "pdf":
        assert contract.technical_structure["pdf"]["pdf_version"]
        assert contract.technical_structure["pdf"]["object_count"] >= 1
        assert any(
            step["code"] == "pdf_structure" and step["status"] == "success"
            for step in contract.processing_steps
        )


def test_engine_failure_does_not_modify_original_evidence(tmp_path: Path) -> None:
    evidence = tmp_path / "failure.bin"
    evidence.write_bytes(b"immutable evidence")
    before = evidence.read_bytes()

    class FailingAnalyzer:
        def analyze_acquired(self, acquired):
            assert acquired.working_path.read_bytes() == before
            raise RuntimeError("synthetic engine failure")

    service = AnalysisService(
        FailingAnalyzer(),
        evidence_manager=EvidenceManager(tmp_path / "workspaces"),
    )

    with pytest.raises(RuntimeError, match="synthetic engine failure"):
        service.analyze(evidence)

    assert evidence.read_bytes() == before


def test_staging_acquisition_and_post_analysis_hashes_are_identical(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORENSIHASH_TEMP_DIR", str(tmp_path / "runtime"))
    evidence = tmp_path / "upload.txt"
    evidence.write_bytes(b"end-to-end identity")
    staging_sha256 = _digest(evidence)

    execution = ApplicationFactory.create_analysis_coordinator().execute(evidence)

    assert execution.legacy_result.evidence_source is not None
    assert execution.legacy_result.evidence_source.initial_sha256 == staging_sha256
    assert execution.contract.hashes["sha256"] == staging_sha256
    assert _digest(evidence) == staging_sha256

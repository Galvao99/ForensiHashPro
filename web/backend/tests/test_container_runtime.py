from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.engines.metadata_engine import MetadataEngine
from app.evidence import CaptureState, EvidenceManager
from app.processing import ProcessingStatus
from app.services.json_parser_service import JsonParserService
from app.services.text_extraction_service import TextExtractionService
from app.settings import ApplicationPaths, ToolDetector


pytestmark = pytest.mark.skipif(
    os.environ.get("FORENSIHASH_CONTAINER_TESTS") != "1",
    reason="smoke tests das dependências nativas da imagem",
)


def test_container_runs_non_root_and_manages_evidence_workspace(
    tmp_path: Path,
) -> None:
    assert os.name == "posix"
    assert os.geteuid() != 0
    source = tmp_path / "evidence.txt"
    source.write_text("ForensiHash container", encoding="utf-8")
    manager = EvidenceManager(workspace_root=tmp_path / "evidence-workspaces")

    with manager.acquire(source) as lease:
        assert lease.source.working_path != source
        assert lease.source.working_path.is_file()
        assert lease.verify().capture_state is CaptureState.VERIFIED
        workspace = lease.workspace

    assert not workspace.exists()
    assert ApplicationPaths.discover().temp_dir.is_dir()


def test_container_detects_external_tools() -> None:
    detector = ToolDetector()

    assert detector.exiftool().available
    assert detector.tesseract().available
    assert detector.poppler().available
    assert detector.rust_core().available


def test_real_exiftool_extracts_synthetic_image(tmp_path: Path) -> None:
    from PIL import Image

    image_path = tmp_path / "synthetic.png"
    Image.new("RGB", (32, 32), "white").save(image_path)

    step = MetadataEngine(timeout_seconds=15).extract_step(image_path)

    assert step.status is ProcessingStatus.SUCCESS
    assert step.value is not None
    assert step.value.raw


def test_real_tesseract_processes_synthetic_image(tmp_path: Path) -> None:
    from PIL import Image, ImageDraw

    image_path = tmp_path / "ocr.png"
    image = Image.new("RGB", (500, 120), "white")
    ImageDraw.Draw(image).text((20, 40), "FORENSIHASH", fill="black")
    image.save(image_path)

    step = TextExtractionService().extract(image_path)

    assert step.status in {ProcessingStatus.SUCCESS, ProcessingStatus.NO_FINDINGS}
    assert step.value is not None
    assert step.value.pages_processed == 1


def test_real_poppler_renders_synthetic_pdf(tmp_path: Path) -> None:
    import fitz
    from pdf2image import convert_from_path

    pdf_path = tmp_path / "synthetic.pdf"
    document = fitz.open()
    document.new_page().insert_text((72, 72), "ForensiHash")
    document.save(pdf_path)
    document.close()

    poppler = ToolDetector().poppler()
    pages = convert_from_path(
        pdf_path,
        first_page=1,
        last_page=1,
        poppler_path=str(poppler.path) if poppler.path else None,
    )

    assert len(pages) == 1


def test_rust_parser_processes_synthetic_json(tmp_path: Path) -> None:
    json_path = tmp_path / "synthetic.json"
    json_path.write_text('{"document": "synthetic"}', encoding="utf-8")

    step = JsonParserService().parse_step(json_path)

    assert step.status is ProcessingStatus.SUCCESS
    assert step.value is not None
    assert step.value.is_valid is True

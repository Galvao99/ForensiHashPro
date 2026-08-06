from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image

from app.engines.binary_structure_engine import BinaryStructureEngine
from app.binary.parsers import PdfRawParser
from app.engines.metadata_engine import MetadataEngine
from app.evidence import EvidenceManager, EvidenceSizeLimitError
from app.processing import ProcessingStatus, StepResult
from app.processing.logging import log_step
from app.services.text_extraction_service import TextExtractionService
from app.settings import ProcessingLimits, ToolState, ToolStatus


def _tool(
    name: str,
    state: ToolState,
    path: Path | None = None,
) -> ToolStatus:
    return ToolStatus(name, state, path, f"{name}: {state.value}")


def _pdf(path: Path, pages: int) -> None:
    document = fitz.open()
    for _ in range(pages):
        document.new_page()
    document.save(path)
    document.close()


def test_tesseract_absent_is_unavailable_not_no_text(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    Image.new("RGB", (10, 10)).save(image)
    service = TextExtractionService(
        tesseract_status=_tool("Tesseract", ToolState.NOT_INSTALLED),
        poppler_status=_tool("Poppler", ToolState.AVAILABLE, tmp_path),
    )

    step = service.extract(image)

    assert step.status is ProcessingStatus.UNAVAILABLE
    assert step.issues[0].code == "ocr_tool_unavailable"
    assert "não está disponível" in step.user_message


def test_poppler_absent_is_unavailable_for_scanned_pdf(tmp_path: Path) -> None:
    pdf = tmp_path / "scan.pdf"
    _pdf(pdf, 1)
    service = TextExtractionService(
        tesseract_status=_tool("Tesseract", ToolState.AVAILABLE, tmp_path / "t.exe"),
        poppler_status=_tool("Poppler", ToolState.NOT_INSTALLED),
    )

    step = service.extract(pdf)

    assert step.status is ProcessingStatus.UNAVAILABLE
    assert step.value is not None and step.value.source == "unavailable"
    assert "Poppler" in step.user_message


def test_exiftool_absent_is_unavailable(tmp_path: Path) -> None:
    engine = MetadataEngine(
        tool_status=_tool("ExifTool", ToolState.NOT_INSTALLED)
    )

    step = engine.extract_step(tmp_path / "evidence.bin")

    assert step.status is ProcessingStatus.UNAVAILABLE
    assert step.value is None


def test_exiftool_timeout_is_explicit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "exiftool.exe"
    executable.write_bytes(b"placeholder")
    engine = MetadataEngine(
        tool_status=_tool("ExifTool", ToolState.AVAILABLE, executable),
        timeout_seconds=1,
    )
    monkeypatch.setattr(
        "app.engines.metadata_engine.subprocess.run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired("exiftool", 1)
        ),
    )

    step = engine.extract_step(tmp_path / "evidence.bin")

    assert step.status is ProcessingStatus.FAILED
    assert step.issues[0].code == "metadata_timeout"
    assert "tempo máximo" in step.user_message


def test_exiftool_error_return_has_safe_message_without_stderr(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "exiftool.exe"
    executable.write_bytes(b"placeholder")
    engine = MetadataEngine(
        tool_status=_tool("ExifTool", ToolState.AVAILABLE, executable)
    )
    secret_stderr = "token=must-not-leak document-personal-data"
    monkeypatch.setattr(
        "app.engines.metadata_engine.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            args=[], returncode=9, stdout="", stderr=secret_stderr
        ),
    )

    step = engine.extract_step(tmp_path / "evidence.bin")

    assert step.status is ProcessingStatus.FAILED
    assert secret_stderr not in step.user_message
    assert secret_stderr not in step.technical_message
    assert step.safe_details == {}


def test_ocr_partial_preserves_successful_page(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = tmp_path / "scan.pdf"
    _pdf(pdf, 2)
    service = TextExtractionService(
        tesseract_status=_tool("Tesseract", ToolState.AVAILABLE, tmp_path / "t.exe"),
        poppler_status=_tool("Poppler", ToolState.AVAILABLE, tmp_path),
    )
    fake_image = SimpleNamespace(size=(100, 100))
    pdf2image = SimpleNamespace(convert_from_path=lambda *_args, **_kwargs: [fake_image])
    calls = 0

    def image_to_string(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("sensitive engine failure")
        return "texto preservado da página 1"

    pytesseract = SimpleNamespace(
        pytesseract=SimpleNamespace(tesseract_cmd=""),
        image_to_string=image_to_string,
    )

    def import_module(name: str):
        return pdf2image if name == "pdf2image" else pytesseract

    monkeypatch.setattr(
        "app.services.text_extraction_service.importlib.import_module",
        import_module,
    )

    step = service.extract(pdf)

    assert step.status is ProcessingStatus.PARTIAL
    assert step.value is not None
    assert "texto preservado" in step.value.text
    assert step.value.pages_processed == 1
    assert step.issues[0].details["page"] == 2
    assert "sensitive engine failure" not in step.user_message


def test_file_above_limit_is_blocked_before_copy(tmp_path: Path) -> None:
    original = tmp_path / "large.bin"
    original.write_bytes(b"12345")
    manager = EvidenceManager(tmp_path / "work", max_file_size_bytes=4)

    with pytest.raises(EvidenceSizeLimitError, match="limite de segurança"):
        manager.acquire(original)

    assert not (tmp_path / "work").exists()


def test_image_pixel_limit_is_not_reported_as_no_text(tmp_path: Path) -> None:
    image = tmp_path / "large.png"
    Image.new("RGB", (11, 11)).save(image)
    service = TextExtractionService(
        tesseract_status=_tool("Tesseract", ToolState.AVAILABLE, tmp_path / "t.exe"),
        limits=ProcessingLimits(max_image_pixels=100),
    )

    step = service.extract(image)

    assert step.status is ProcessingStatus.LIMIT_EXCEEDED
    assert step.issues[0].code == "ocr_image_limit"


def test_pdf_page_limit_is_explicit(tmp_path: Path) -> None:
    pdf = tmp_path / "large.pdf"
    _pdf(pdf, 2)
    service = TextExtractionService(limits=ProcessingLimits(max_pdf_pages=1))

    step = service.extract(pdf)

    assert step.status is ProcessingStatus.LIMIT_EXCEEDED
    assert step.issues[0].details == {"pages": 2, "limit": 1}


def test_binary_component_failure_is_partial_and_other_results_survive(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"printable technical content")

    class FailingScanner:
        def scan(self, *_args, **_kwargs):
            raise RuntimeError("scanner internal detail")

    result = BinaryStructureEngine(signature_scanner=FailingScanner()).analyze(path)

    failed = next(step for step in result.processing_steps if step.code == "signature_scan")
    assert failed.status is ProcessingStatus.FAILED
    assert failed.issues[0].original_exception is not None
    assert "scanner internal detail" not in failed.user_message
    assert result.strings
    assert any(step.status is ProcessingStatus.SUCCESS for step in result.processing_steps)


def test_pdf_object_limit_is_recorded_without_losing_other_binary_results(
    tmp_path: Path,
) -> None:
    path = tmp_path / "many-objects.pdf"
    path.write_bytes(
        b"%PDF-1.7\n1 0 obj\nendobj\n2 0 obj\nendobj\n%%EOF"
    )
    engine = BinaryStructureEngine(pdf_raw_parser=PdfRawParser(max_objects=1))

    result = engine.analyze(path)

    pdf_step = next(step for step in result.processing_steps if step.code == "pdf_raw_parser")
    assert pdf_step.status is ProcessingStatus.LIMIT_EXCEEDED
    assert result.header_bytes.startswith(b"%PDF")
    assert result.pdf_raw_analysis is None


def test_structured_log_does_not_include_secret_or_messages(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "API-SECRET-MUST-NOT-APPEAR"
    step = StepResult(
        code="external_lookup",
        component="ip",
        status=ProcessingStatus.FAILED,
        technical_message=secret,
        user_message=secret,
    )
    logger = logging.getLogger("test.safe.processing")

    with caplog.at_level(logging.INFO, logger=logger.name):
        log_step(logger, step, analysis_id="analysis-1", evidence_id="evidence-1")

    assert "processing_step" in caplog.text
    assert secret not in caplog.text
    record = caplog.records[-1]
    assert record.analysis_id == "analysis-1"
    assert record.evidence_id == "evidence-1"

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.engines.binary_structure_engine import BinaryStructureEngine


@pytest.mark.parametrize(
    "content",
    [
        b"",
        b"ordinary generic content",
        b"%PDF-1.7\ntext\n%%EOF",
        b"prefix\xff\xd8\xffembedded image candidate",
    ],
)
def test_engine_builds_complete_result(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(content)
    result = BinaryStructureEngine(
        header_size=8,
        footer_size=6,
        entropy_block_size=4,
        string_minimum_length=4,
    ).analyze(path)
    assert result.file_size == len(content)
    assert result.header_bytes == content[:8]
    assert result.footer_bytes == (content[-6:] if content else b"")
    assert isinstance(result.regions, list)
    assert isinstance(result.strings, list)
    assert isinstance(result.entropy_regions, list)
    if content:
        assert result.average_entropy is not None
    else:
        assert result.average_entropy is None


def test_pdf_and_internal_jpeg_regions(tmp_path: Path) -> None:
    path = tmp_path / "mixed.bin"
    path.write_bytes(b"%PDF-1.7\ntext\xff\xd8\xffdata")
    result = BinaryStructureEngine().analyze(path)
    assert result.regions[0].kind == "pdf"
    assert any(region.kind == "candidate_jpeg" for region in result.regions)
    assert any(item.value.startswith("%PDF") for item in result.strings)


class _FailingScanner:
    def scan(self, reader, max_results_per_signature):
        raise RuntimeError("scanner unavailable")


def test_partial_failure_is_recorded(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"printable content")
    result = BinaryStructureEngine(signature_scanner=_FailingScanner()).analyze(path)
    assert result.regions == []
    assert result.strings
    assert result.entropy_regions
    assert result.findings[0].code == "signature_scan_failed"
    assert result.findings[0].evidence["error_type"] == "RuntimeError"


def test_pdf_raw_parser_runs_only_for_technical_pdf(tmp_path: Path) -> None:
    pdf_path = tmp_path / "renamed.bin"
    pdf_path.write_bytes(b"prefix\n%PDF-1.7\n%%EOF")
    pdf_result = BinaryStructureEngine().analyze(pdf_path)
    assert pdf_result.parser_name == "pdf_raw"
    assert pdf_result.pdf_raw_analysis is not None
    assert pdf_result.pdf_raw_analysis.header_offset == 7

    non_pdf_path = tmp_path / "misleading.pdf"
    non_pdf_path.write_bytes(b"ordinary content")
    non_pdf_result = BinaryStructureEngine().analyze(non_pdf_path)
    assert non_pdf_result.parser_name is None
    assert non_pdf_result.pdf_raw_analysis is None

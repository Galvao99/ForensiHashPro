from pathlib import Path
from types import SimpleNamespace

import pytest

from app.engines.file_analyzer import FileAnalyzer
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.pdf_structure_engine import PDFStructureEngine


def _analyzer() -> FileAnalyzer:
    return FileAnalyzer(
        hash_engine=None,
        metadata_engine=None,
        findings_engine=None,
        magic_number_engine=None,
        digital_signature_engine=None,
        pdf_structure_engine=None,
    )


def _valid_structure() -> SimpleNamespace:
    return SimpleNamespace(
        header_valid=True,
        eof_valid=True,
        eof_count=1,
        encrypted=False,
        javascript_detected=False,
        embedded_files=False,
        xref_found=True,
        trailer_found=True,
        incremental_updates=0,
    )


@pytest.mark.parametrize(
    ("file_name", "content", "expected_verified"),
    [
        ("image.png", b"\x89PNG\r\n\x1a\n", True),
        ("image.jpg", b"\x89PNG\r\n\x1a\n", False),
        ("unknown.bin", b"not-a-known-signature", False),
    ],
)
def test_magic_number_verification_uses_extension_matches(
    tmp_path: Path,
    file_name: str,
    content: bytes,
    expected_verified: bool,
) -> None:
    file_path = tmp_path / file_name
    file_path.write_bytes(content)
    magic_numbers = MagicNumberEngine().analyze(file_path)

    integrity = _analyzer()._build_integrity_result(
        hashes=SimpleNamespace(sha256="hash"),
        magic_numbers=magic_numbers,
        digital_signature=SimpleNamespace(has_signature=True),
        pdf_structure=_valid_structure(),
    )

    assert magic_numbers.extension_matches is expected_verified
    assert integrity.magic_number_verified is expected_verified
    assert integrity.score is None
    assert integrity.is_structurally_valid is None


def test_valid_pdf_confirms_magic_number_and_structural_validity(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "valid.pdf"
    file_path.write_bytes(
        b"%PDF-1.7\n"
        b"1 0 obj\n<<>>\nendobj\n"
        b"xref\n0 1\n"
        b"trailer\n<<>>\n"
        b"startxref\n0\n"
        b"%%EOF\n"
    )

    magic_numbers = MagicNumberEngine().analyze(file_path)
    pdf_structure = PDFStructureEngine().analyze(file_path)

    integrity = _analyzer()._build_integrity_result(
        hashes=SimpleNamespace(sha256="hash"),
        magic_numbers=magic_numbers,
        digital_signature=SimpleNamespace(has_signature=False),
        pdf_structure=pdf_structure,
    )

    assert magic_numbers.detected_format == "PDF"
    assert magic_numbers.extension_matches is True
    assert integrity.magic_number_verified is True
    assert integrity.score is None
    assert integrity.is_structurally_valid is None

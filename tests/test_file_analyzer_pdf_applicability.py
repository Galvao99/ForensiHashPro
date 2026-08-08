from pathlib import Path
from types import SimpleNamespace

import pytest

from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.models import MetadataResult


PDF_CONTENT = (
    b"%PDF-1.7\n"
    b"1 0 obj\n<<>>\nendobj\n"
    b"xref\n0 1\n"
    b"trailer\n<<>>\n"
    b"startxref\n0\n"
    b"%%EOF\n"
)


class _MetadataEngine:
    def extract(self, file_path: Path) -> MetadataResult:
        return MetadataResult(raw={"SourceFile": str(file_path)})


class _DigitalSignatureEngine:
    def analyze(self, file_path: Path) -> SimpleNamespace:
        return SimpleNamespace(has_signature=False)


class _JsonParserService:
    def parse(self, file_path: Path) -> SimpleNamespace:
        return SimpleNamespace(is_valid=True)


class _RecordingPDFStructureEngine:
    def __init__(self) -> None:
        self.calls: list[Path] = []
        self.delegate = PDFStructureEngine()

    def analyze(self, file_path: Path):
        self.calls.append(file_path)
        return self.delegate.analyze(file_path)


def _analyze(
    tmp_path: Path,
    file_name: str,
    content: bytes,
):
    file_path = tmp_path / file_name
    file_path.write_bytes(content)
    pdf_structure_engine = _RecordingPDFStructureEngine()
    analyzer = FileAnalyzer(
        hash_engine=HashEngine(),
        metadata_engine=_MetadataEngine(),
        findings_engine=FindingsEngine(),
        magic_number_engine=MagicNumberEngine(),
        digital_signature_engine=_DigitalSignatureEngine(),
        pdf_structure_engine=pdf_structure_engine,
        json_parser_service=_JsonParserService(),
    )

    return analyzer.analyze_fixture(file_path), pdf_structure_engine.calls


@pytest.mark.parametrize(
    ("file_name", "content"),
    [
        ("image.jpg", b"\xff\xd8\xffimage"),
        ("data.json", b'{"key": "value"}'),
        ("archive.zip", b"PK\x03\x04archive"),
        ("renamed.pdf", b"\xff\xd8\xffimage"),
    ],
)
def test_non_pdf_skips_pdf_structure_as_not_applicable(
    tmp_path: Path,
    file_name: str,
    content: bytes,
) -> None:
    result, calls = _analyze(
        tmp_path,
        file_name,
        content,
    )

    assert calls == []
    assert result.integrity.score is None
    assert result.integrity.technical_status == (
        "Score agregado desativado; consulte separadamente hash, tipo real, "
        "estrutura observada, assinatura, metadados e limitações."
    )
    assert result.integrity.is_structurally_valid is None
    assert result.integrity.header_valid is None
    assert result.integrity.eof_valid is None
    assert result.integrity.xref_valid is None
    assert result.integrity.trailer_valid is None
    assert not any(
        term in finding.title.lower()
        for finding in result.findings
        for term in ("header", "eof", "xref", "trailer")
    )


@pytest.mark.parametrize(
    "file_name",
    [
        "document.pdf",
        "document.bin",
    ],
)
def test_technical_pdf_runs_pdf_structure_regardless_of_extension(
    tmp_path: Path,
    file_name: str,
) -> None:
    result, calls = _analyze(
        tmp_path,
        file_name,
        PDF_CONTENT,
    )

    assert len(calls) == 1
    assert result.magic_numbers.detected_format == "PDF"
    assert result.integrity.score is None
    assert result.integrity.technical_status == (
        "Score agregado desativado; consulte separadamente hash, tipo real, "
        "estrutura observada, assinatura, metadados e limitações."
    )
    assert result.integrity.is_structurally_valid is None
    assert result.integrity.header_valid is True
    assert result.integrity.eof_valid is True
    assert result.integrity.xref_valid is True
    assert result.integrity.trailer_valid is True

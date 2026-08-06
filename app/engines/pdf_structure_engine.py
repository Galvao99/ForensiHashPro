import re
from pathlib import Path

from app.models.pdf_structure_result import PDFStructureResult


class PDFStructureEngine:
    """Registra marcadores PDF sem declarar validade estrutural do documento."""

    _TRADITIONAL_XREF = re.compile(
        rb"(?m)^[\x00\x09\x0c\x20]*xref[\x00\x09\x0c\x20]*(?:\r?$)"
    )
    _XREF_STREAM = re.compile(rb"/Type\s*/XRef\b")

    def analyze(self, file_path: Path) -> PDFStructureResult:
        data = file_path.read_bytes()

        header = data[:1024]
        pdf_version = self._extract_pdf_version(header)
        eof_count = data.count(b"%%EOF")
        traditional_xref_found = bool(self._TRADITIONAL_XREF.search(data))
        xref_stream_found = bool(self._XREF_STREAM.search(data))
        limitations = (
            "A presença de marcadores não equivale a uma validação completa da estrutura PDF.",
            "Marcadores em streams comprimidos podem não ser observados por esta etapa básica.",
        )

        return PDFStructureResult(
            pdf_version=pdf_version,
            header_valid=pdf_version is not None,
            eof_count=eof_count,
            eof_valid=eof_count >= 1,
            xref_found=traditional_xref_found or xref_stream_found,
            trailer_found=b"trailer" in data,
            startxref_found=b"startxref" in data,
            encrypted=b"/Encrypt" in data,
            javascript_detected=(
                b"/JavaScript" in data
                or b"/JS" in data
                or b"/OpenAction" in data
                or b"/AA" in data
            ),
            embedded_files=(
                b"/EmbeddedFiles" in data
                or b"/Filespec" in data
                or b"/EF" in data
            ),
            acroform_found=b"/AcroForm" in data,
            incremental_updates=max(0, eof_count - 1),
            object_count=len(re.findall(rb"(?m)^\s*\d+\s+\d+\s+obj\b", data)),
            stream_count=len(re.findall(rb"(?m)^\s*stream(?:\r?$)", data)),
            linearized=b"/Linearized" in data,
            traditional_xref_found=traditional_xref_found,
            xref_stream_found=xref_stream_found,
            parser_limitations=limitations,
        )

    def _extract_pdf_version(self, header: bytes) -> str | None:
        marker = b"%PDF-"

        index = header.find(marker)

        if index == -1:
            return None

        start = index + len(marker)
        version = header[start : start + 3].decode("latin-1", errors="ignore")

        return version

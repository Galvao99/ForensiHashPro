from pathlib import Path

from app.models.pdf_structure_result import PDFStructureResult


class PDFStructureEngine:
    """Analisa a estrutura básica de arquivos PDF a partir dos bytes."""

    def analyze(self, file_path: Path) -> PDFStructureResult:
        data = file_path.read_bytes()

        header = data[:1024]
        full_text = data.decode("latin-1", errors="ignore")

        pdf_version = self._extract_pdf_version(header)

        eof_count = full_text.count("%%EOF")

        return PDFStructureResult(
            pdf_version=pdf_version,
            header_valid=pdf_version is not None,
            eof_count=eof_count,
            eof_valid=eof_count >= 1,
            xref_found="xref" in full_text,
            trailer_found="trailer" in full_text,
            startxref_found="startxref" in full_text,
            encrypted="/Encrypt" in full_text,
            javascript_detected=(
                "/JavaScript" in full_text
                or "/JS" in full_text
                or "/OpenAction" in full_text
                or "/AA" in full_text
            ),
            embedded_files=(
                "/EmbeddedFiles" in full_text
                or "/Filespec" in full_text
                or "/EF" in full_text
            ),
            acroform_found="/AcroForm" in full_text,
            incremental_updates=max(0, eof_count - 1),
            object_count=full_text.count(" obj"),
            stream_count=full_text.count("stream"),
            linearized="/Linearized" in full_text,
        )

    def _extract_pdf_version(self, header: bytes) -> str | None:
        marker = b"%PDF-"

        index = header.find(marker)

        if index == -1:
            return None

        start = index + len(marker)
        version = header[start : start + 3].decode("latin-1", errors="ignore")

        return version
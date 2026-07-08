from dataclasses import dataclass


@dataclass(frozen=True)
class PDFStructureResult:

    pdf_version: str | None
    header_valid: bool
    eof_count: int
    eof_valid: bool
    xref_found: bool
    trailer_found: bool
    startxref_found: bool
    encrypted: bool
    javascript_detected: bool
    embedded_files: bool
    acroform_found: bool
    incremental_updates: int
    object_count: int
    stream_count: int
    linearized: bool
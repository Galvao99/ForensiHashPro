from dataclasses import dataclass, field

from app.models.binary_finding import BinaryFinding


@dataclass(frozen=True, slots=True)
class PdfRawObject:
    object_number: int
    generation_number: int
    start_offset: int
    end_offset: int | None
    has_stream: bool


@dataclass(frozen=True, slots=True)
class PdfStartXref:
    marker_offset: int
    declared_offset: int | None


@dataclass(slots=True)
class PdfRawAnalysisResult:
    version: str | None = None
    header_offset: int | None = None
    objects: list[PdfRawObject] = field(default_factory=list)
    stream_count: int = 0
    xref_offsets: list[int] = field(default_factory=list)
    xref_stream_offsets: list[int] = field(default_factory=list)
    trailer_offsets: list[int] = field(default_factory=list)
    startxrefs: list[PdfStartXref] = field(default_factory=list)
    eof_offsets: list[int] = field(default_factory=list)
    prev_offsets: list[int] = field(default_factory=list)
    encrypted: bool = False
    has_javascript: bool = False
    has_embedded_files: bool = False
    has_open_action: bool = False
    has_additional_actions: bool = False
    has_acroform: bool = False
    has_xfa: bool = False
    bytes_after_last_eof: int = 0
    findings: list[BinaryFinding] = field(default_factory=list)

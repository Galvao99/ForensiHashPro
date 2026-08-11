from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ArtifactIdentification:
    declared_extension: str
    filename: str
    detected_type: str
    mime_type: str
    magic_signature: str
    extension_matches: bool
    confidence: int = 0


@dataclass(frozen=True, slots=True)
class ArchiveWarning:
    code: str
    message: str
    entry_ref: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ArchiveEntry:
    embedded_artifact_ref: str
    filename: str
    internal_path: str
    extension: str
    compressed_size: int
    uncompressed_size: int
    compression_ratio: float | None
    crc32: str
    compression_method: int
    encrypted: bool
    entry_type: str
    detected_type: str | None = None
    mime_type: str | None = None
    magic_signature: str | None = None
    sha256: str | None = None
    inspection_flags: list[str] = field(default_factory=list)
    nested_depth: int = 0
    children: list["ArchiveEntry"] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ArchiveInspectionResult:
    archive_type: str = "ZIP"
    state: str = "completed"
    total_entries: int = 0
    directory_entries: int = 0
    total_compressed_size: int = 0
    declared_uncompressed_size: int = 0
    inspected_uncompressed_bytes: int = 0
    max_depth: int = 0
    encrypted_entries: int = 0
    executable_entries: int = 0
    script_entries: int = 0
    macro_enabled_entries: int = 0
    entries: list[ArchiveEntry] = field(default_factory=list)
    warnings: list[ArchiveWarning] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ParsedArtifact:
    parser_id: str
    detected_type: str
    declared_extension: str
    mime_type: str
    magic_signature: str
    state: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)
    structure: dict[str, Any] = field(default_factory=dict)
    embedded_artifacts: list[ArchiveEntry] = field(default_factory=list)
    warnings: list[ArchiveWarning] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


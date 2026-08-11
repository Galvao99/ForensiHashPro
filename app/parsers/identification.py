from __future__ import annotations

from pathlib import Path

from app.models.magic_number_result import MagicNumberResult
from app.parsers.models import ArtifactIdentification


def identify_artifact(path: Path, magic: MagicNumberResult) -> ArtifactIdentification:
    return ArtifactIdentification(
        declared_extension=Path(path).suffix.lower(),
        filename=Path(path).name,
        detected_type=str(magic.detected_format or magic.detected_type or "UNKNOWN").upper(),
        mime_type=magic.mime_type,
        magic_signature=magic.signature,
        extension_matches=magic.extension_matches,
        confidence=magic.confidence,
    )


def identify_bytes(header: bytes) -> tuple[str, str, str] | None:
    signatures = (
        (b"%PDF-", "PDF", "application/pdf"),
        (b"MZ", "PE", "application/vnd.microsoft.portable-executable"),
        (b"\xFF\xD8\xFF", "JPEG", "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n", "PNG", "image/png"),
        (b"PK\x03\x04", "ZIP", "application/zip"),
        (b"PK\x05\x06", "ZIP", "application/zip"),
        (b"{", "JSON", "application/json"),
        (b"[", "JSON", "application/json"),
    )
    stripped = header.lstrip()
    for signature, detected, mime in signatures:
        candidate = stripped if detected == "JSON" else header
        if candidate.startswith(signature):
            return detected, mime, signature.hex(" ").upper()
    return None


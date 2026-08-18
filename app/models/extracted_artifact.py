from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class ExtractedArtifact:
    source_path: Path
    destination_path: Path
    source_sha256: str
    start_offset: int
    end_offset: int
    length: int
    extracted_sha256: str
    detected_format: str
    detected_mime: str
    signature: str
    extraction_method: str = "hex_selection"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["source_path"] = str(self.source_path)
        value["destination_path"] = str(self.destination_path)
        value["created_at"] = self.created_at.isoformat()
        return value

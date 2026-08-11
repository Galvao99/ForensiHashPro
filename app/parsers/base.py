from __future__ import annotations

from pathlib import Path
from typing import Protocol

from app.parsers.models import ArtifactIdentification, ParsedArtifact


class ArtifactParser(Protocol):
    parser_id: str
    supported_types: frozenset[str]
    priority: int

    def can_parse(self, identification: ArtifactIdentification) -> bool: ...

    def parse(
        self, path: Path, identification: ArtifactIdentification
    ) -> ParsedArtifact: ...


from __future__ import annotations

from pathlib import Path

from app.parsers.base import ArtifactParser
from app.parsers.models import ArtifactIdentification, ParsedArtifact


class ParserRegistry:
    """Registro explícito; nunca importa código com base em dados do artefato."""

    def __init__(
        self,
        parsers: list[ArtifactParser] | None = None,
        fallback: ArtifactParser | None = None,
    ) -> None:
        self._parsers: list[ArtifactParser] = []
        self.fallback = fallback or BinaryFallbackParser()
        for parser in parsers or []:
            self.register(parser)

    def register(self, parser: ArtifactParser) -> None:
        if any(item.parser_id == parser.parser_id for item in self._parsers):
            raise ValueError(f"Parser duplicado: {parser.parser_id}")
        self._parsers.append(parser)
        self._parsers.sort(key=lambda item: (-item.priority, item.parser_id))

    def select(self, identification: ArtifactIdentification) -> ArtifactParser:
        return next(
            (parser for parser in self._parsers if parser.can_parse(identification)),
            self.fallback,
        )

    def parse(self, path: Path, identification: ArtifactIdentification) -> ParsedArtifact:
        return self.select(identification).parse(Path(path), identification)


class BinaryFallbackParser:
    parser_id = "binary_fallback"
    supported_types = frozenset({"UNKNOWN"})
    priority = -10_000

    def can_parse(self, identification: ArtifactIdentification) -> bool:
        return True

    def parse(self, path: Path, identification: ArtifactIdentification) -> ParsedArtifact:
        return ParsedArtifact(
            parser_id=self.parser_id,
            detected_type=identification.detected_type,
            declared_extension=identification.declared_extension,
            mime_type=identification.mime_type,
            magic_signature=identification.magic_signature,
            state="completed",
            limitations=[
                "Formato não reconhecido ou parser especializado indisponível; "
                "a análise binária geral permanece aplicável."
            ],
        )


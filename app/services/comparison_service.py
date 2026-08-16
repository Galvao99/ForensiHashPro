from __future__ import annotations

from collections import defaultdict
from difflib import ndiff
from pathlib import Path
from typing import Any, Iterable

from app.engines.comparison_engine import ComparisonEngine
from app.models import AnalysisResult
from app.models.comparison_view import ComparisonView, DiffField, DiffGroup


class ComparisonService:
    """Compara somente o par solicitado usando resultados já produzidos."""

    def __init__(self, engine: ComparisonEngine | None = None) -> None:
        self._engine = engine or ComparisonEngine()

    def compare(self, left: AnalysisResult, right: AnalysisResult) -> ComparisonView:
        engine_result = self._engine.compare(left, right)
        groups = tuple(group for group in self._groups(left, right) if group.fields)
        matches: list[tuple[str, str, str]] = []
        for group in groups:
            for field in group.fields:
                if field.state == "match" and field.left not in (None, ""):
                    matches.append((group.title, field.key, field.left))
        return ComparisonView(
            artifact_id(left), artifact_id(right), groups, tuple(matches), engine_result
        )

    def comparable_dimensions(
        self, left: AnalysisResult, right: AnalysisResult
    ) -> tuple[tuple[str, bool], ...]:
        return (
            ("Hashes", True),
            ("Metadados", bool(left.metadata.raw or right.metadata.raw)),
            ("Estrutura", bool(left.pdf_structure and right.pdf_structure)),
            ("Assinaturas", bool(left.digital_signature and right.digital_signature)),
            ("Texto", bool(left.has_extracted_text and right.has_extracted_text)),
            ("Entidades", bool(left.resolved_entities and right.resolved_entities)),
            ("Timeline", bool(left.timeline_events and right.timeline_events)),
        )

    def _groups(self, left: AnalysisResult, right: AnalysisResult) -> Iterable[DiffGroup]:
        yield DiffGroup("Resumo", (
            self._field("Arquivo", left.file_info.name, right.file_info.name),
            self._field("Formato", self._format(left), self._format(right)),
            self._field("Tamanho", str(left.file_info.size_bytes), str(right.file_info.size_bytes)),
        ))
        yield DiffGroup("Hashes", tuple(
            self._field(name.upper(), getattr(left.hashes, name), getattr(right.hashes, name))
            for name in ("sha256", "sha1", "md5")
        ))
        keys = sorted(set(left.metadata.raw) | set(right.metadata.raw), key=str.casefold)
        yield DiffGroup("Metadados", tuple(
            self._field(str(key), self._value(left.metadata.raw.get(key)), self._value(right.metadata.raw.get(key)))
            for key in keys
        ))
        yield self._structure(left, right)
        yield self._signature(left, right)
        yield self._text(left, right)
        yield self._entities(left, right)
        yield self._timeline(left, right)

    def _structure(self, left: AnalysisResult, right: AnalysisResult) -> DiffGroup:
        if not left.pdf_structure or not right.pdf_structure:
            return DiffGroup("Estrutura")
        names = ("object_count", "stream_count", "incremental_updates", "xref_stream_found", "encrypted")
        return DiffGroup("Estrutura", tuple(
            self._field(name.replace("_", " ").title(), self._value(getattr(left.pdf_structure, name)), self._value(getattr(right.pdf_structure, name)))
            for name in names
        ))

    def _signature(self, left: AnalysisResult, right: AnalysisResult) -> DiffGroup:
        names = ("has_signature", "signature_count", "signer", "issuer", "serial_number", "algorithm", "signing_time", "technical_status")
        return DiffGroup("Assinaturas", tuple(
            self._field(name.replace("_", " ").title(), self._value(getattr(left.digital_signature, name)), self._value(getattr(right.digital_signature, name)))
            for name in names
        ))

    def _text(self, left: AnalysisResult, right: AnalysisResult) -> DiffGroup:
        if not left.has_extracted_text or not right.has_extracted_text:
            return DiffGroup("Texto")
        fields: list[DiffField] = []
        index = 0
        for line in ndiff(left.extracted_text.splitlines(), right.extracted_text.splitlines()):
            if line.startswith("? "):
                continue
            index += 1
            if line.startswith("  "):
                fields.append(DiffField(f"Linha {index}", line[2:], line[2:], "match"))
            elif line.startswith("- "):
                fields.append(DiffField(f"Linha {index}", line[2:], None, "left_only"))
            elif line.startswith("+ "):
                fields.append(DiffField(f"Linha {index}", None, line[2:], "right_only"))
        return DiffGroup("Texto", tuple(fields))

    def _entities(self, left: AnalysisResult, right: AnalysisResult) -> DiffGroup:
        def collect(result: AnalysisResult) -> dict[str, set[str]]:
            values: dict[str, set[str]] = defaultdict(set)
            for entity in result.resolved_entities:
                kind = getattr(entity.entity_type, "value", str(entity.entity_type)).upper()
                values[kind].add(entity.normalized_value)
            return values
        a, b = collect(left), collect(right)
        fields: list[DiffField] = []
        for kind in sorted(set(a) | set(b)):
            for value in sorted(a[kind] | b[kind]):
                fields.append(self._field(kind, value if value in a[kind] else None, value if value in b[kind] else None))
        return DiffGroup("Entidades", tuple(fields))

    def _timeline(self, left: AnalysisResult, right: AnalysisResult) -> DiffGroup:
        def collect(result: AnalysisResult) -> dict[str, str]:
            return {f"{event.event_type} · {event.title}": event.timestamp or event.raw_timestamp or "Sem data determinada" for event in result.timeline_events}
        a, b = collect(left), collect(right)
        return DiffGroup("Timeline", tuple(self._field(key, a.get(key), b.get(key)) for key in sorted(set(a) | set(b))))

    @staticmethod
    def _field(key: str, left: str | None, right: str | None) -> DiffField:
        state = "match" if left == right else "left_only" if right is None else "right_only" if left is None else "changed"
        return DiffField(key, left, right, state)

    @staticmethod
    def _value(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        return str(value)

    @staticmethod
    def _format(result: AnalysisResult) -> str:
        return result.magic_numbers.detected_format or result.file_info.extension.lstrip(".").upper() or "Arquivo"


def artifact_id(result: AnalysisResult) -> str:
    evidence_id = getattr(result.evidence_source, "evidence_id", "")
    if evidence_id:
        return str(evidence_id)
    if result.analysis_id:
        return result.analysis_id
    return str(Path(result.file_info.path).resolve(strict=False)).casefold()

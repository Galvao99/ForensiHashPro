from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import re
from typing import Protocol

from app.correlation.v2.identity import source_file_identity
from app.correlation.v2.models import (
    CorrelationCandidate, CorrelationProvenance, EntityType, SourceFileIdentity,
)
from app.entities.models import EntitySource, EntitySourceType
from app.entities.models import EntityType as ResolvedEntityType
from app.models import AnalysisResult
from app.models.extracted_artifact import ExtractedArtifact


class CorrelationSourceProvider(Protocol):
    provider_name: str
    capabilities: frozenset[EntityType]

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]: ...


class HashCorrelationProvider:
    provider_name = "hash"
    capabilities = frozenset({EntityType.SHA256, EntityType.MD5})

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        hashes = getattr(result, "hashes", None)
        for field, entity_type in (("sha256", EntityType.SHA256), ("md5", EntityType.MD5)):
            value = getattr(hashes, field, None)
            if value:
                yield CorrelationCandidate(
                    entity_type, str(value), source_file,
                    CorrelationProvenance(engine="hash_engine", field=field),
                )


_RESOLVED_TYPES = {
    ResolvedEntityType.CPF: EntityType.CPF,
    ResolvedEntityType.PHONE: EntityType.PHONE,
    ResolvedEntityType.IP: EntityType.IP,
    ResolvedEntityType.EMAIL: EntityType.EMAIL,
    ResolvedEntityType.DATETIME: EntityType.TIMESTAMP,
}


class _ResolvedSourceProvider:
    source_types: frozenset[EntitySourceType] = frozenset()
    engine_name = "resolved_entity"

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        for entity in getattr(result, "resolved_entities", ()) or ():
            entity_type = _RESOLVED_TYPES.get(entity.entity_type)
            if entity_type is None:
                continue
            for source in sorted(entity.sources, key=_entity_source_key):
                if source.source_type not in self.source_types:
                    continue
                raw = _raw_for_source(result, entity.normalized_value, entity.raw_values, source)
                context = _source_context(source, raw)
                yield CorrelationCandidate(
                    entity_type, raw, source_file,
                    CorrelationProvenance(
                        engine=self.engine_name,
                        source_engine=source.extractor or source.source_type.value,
                        field=source.source_type.value, path=source.field_path,
                        page=source.page, start=source.start, end=source.end,
                    ), context=context,
                )


class TextCorrelationProvider(_ResolvedSourceProvider):
    provider_name = "text"
    capabilities = frozenset(_RESOLVED_TYPES.values())
    source_types = frozenset({EntitySourceType.NATIVE_TEXT})
    engine_name = "text_extraction"


class OcrCorrelationProvider(_ResolvedSourceProvider):
    provider_name = "ocr"
    capabilities = frozenset(_RESOLVED_TYPES.values())
    source_types = frozenset({EntitySourceType.OCR})
    engine_name = "ocr"


class ResolvedEntityCorrelationProvider(_ResolvedSourceProvider):
    provider_name = "resolved_entity"
    capabilities = frozenset(_RESOLVED_TYPES.values())
    source_types = frozenset({EntitySourceType.STRUCTURED, EntitySourceType.LEGACY_TEXT})


class IpCorrelationProvider:
    """Adapter for structured IP occurrences not already represented by resolved entities."""

    provider_name = "ip"
    capabilities = frozenset({EntityType.IP})

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        if any(entity.entity_type is ResolvedEntityType.IP for entity in getattr(result, "resolved_entities", ())):
            return
        for attribute in ("detected_ips", "ips", "ip_addresses"):
            values = getattr(result, attribute, ())
            if not isinstance(values, (list, tuple, set)):
                continue
            ordered = sorted(values, key=lambda item: str(getattr(item, "address", item)))
            for index, item in enumerate(ordered):
                raw = getattr(item, "raw_text", None) or getattr(item, "address", None) or str(item)
                yield CorrelationCandidate(
                    EntityType.IP, raw, source_file,
                    CorrelationProvenance(
                        engine="ip_extraction", field=attribute,
                        start=getattr(item, "start", None), end=getattr(item, "end", None),
                        path=f"{attribute}[{index}]",
                    ), context=getattr(item, "context", None),
                )


class MetadataCorrelationProvider:
    """Conservative adapter: only explicitly mapped deterministic metadata fields."""

    provider_name = "metadata"
    capabilities = frozenset({EntityType.TIMESTAMP, EntityType.FILENAME})
    FIELD_TYPES = {
        "CreateDate": EntityType.TIMESTAMP, "ModifyDate": EntityType.TIMESTAMP,
        "FileName": EntityType.FILENAME, "SourceFile": EntityType.FILENAME,
    }

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        raw = getattr(getattr(result, "metadata", None), "raw", {})
        if not isinstance(raw, dict):
            return
        for field, value in sorted(raw.items(), key=lambda item: str(item[0])):
            leaf = str(field).rsplit(":", 1)[-1]
            entity_type = self.FIELD_TYPES.get(leaf)
            if entity_type is not None and value is not None:
                yield CorrelationCandidate(
                    entity_type, str(value), source_file,
                    CorrelationProvenance(engine="metadata_engine", field=str(field), path=str(field)),
                )


@dataclass(frozen=True, slots=True)
class JsonProviderLimits:
    max_fields: int = 20_000
    max_nodes: int = 20_000
    max_depth: int = 64
    max_string_length: int = 4_096

    def __post_init__(self) -> None:
        if min(self.max_fields, self.max_nodes, self.max_depth, self.max_string_length) < 1:
            raise ValueError("JSON provider limits must be positive.")


class JsonCorrelationProvider:
    provider_name = "json"
    capabilities = frozenset(EntityType)
    _KEY_TYPES = {
        "ip": EntityType.IP, "ipaddress": EntityType.IP, "ip_address": EntityType.IP,
        "email": EntityType.EMAIL, "phone": EntityType.PHONE, "telefone": EntityType.PHONE,
        "cpf": EntityType.CPF, "cnpj": EntityType.CNPJ, "url": EntityType.URL,
        "uri": EntityType.URL, "timestamp": EntityType.TIMESTAMP, "datetime": EntityType.TIMESTAMP,
        "date": EntityType.TIMESTAMP, "created_at": EntityType.TIMESTAMP,
        "updated_at": EntityType.TIMESTAMP, "occurred_at": EntityType.TIMESTAMP,
        "sha256": EntityType.SHA256, "sha_256": EntityType.SHA256, "md5": EntityType.MD5,
        "filename": EntityType.FILENAME, "file_name": EntityType.FILENAME,
        "document_identifier": EntityType.DOCUMENT_IDENTIFIER,
    }

    def __init__(self, limits: JsonProviderLimits | None = None) -> None:
        self.limits = limits or JsonProviderLimits()

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        analysis = getattr(result, "json_analysis", None)
        if analysis is None or not getattr(analysis, "is_valid", False):
            return
        fields = sorted(getattr(analysis, "fields", ()) or (), key=lambda item: (item.path, item.key))
        for item in fields[: min(self.limits.max_fields, self.limits.max_nodes)]:
            if _json_path_depth(item.path) > self.limits.max_depth:
                continue
            if isinstance(item.value, (dict, list, tuple, set, bytes, bool)) or item.value is None:
                continue
            raw = str(item.value).strip()
            if not raw or len(raw) > self.limits.max_string_length:
                continue
            entity_type = self._KEY_TYPES.get(_normalized_key(item.key))
            if entity_type is None:
                continue
            yield CorrelationCandidate(
                entity_type, raw, source_file,
                CorrelationProvenance(
                    engine="json_engine", source_engine="json_parser",
                    field=item.key, path=item.path,
                ), context=f"{item.key}: {raw}",
            )


class TimelineCorrelationProvider:
    provider_name = "timeline"
    capabilities = frozenset({EntityType.TIMESTAMP})

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        events = sorted(
            getattr(result, "timeline_events", ()) or (),
            key=lambda item: (item.timestamp or "", item.event_type, item.event_id),
        )
        for event in events:
            if event.temporal_status == "structural_only":
                continue
            raw = event.raw_timestamp or event.timestamp
            if not raw:
                continue
            yield CorrelationCandidate(
                EntityType.TIMESTAMP, raw, source_file,
                CorrelationProvenance(
                    engine=event.source_engine,
                    source_engine=event.source_type,
                    field=(str(event.attributes.get("key"))
                           if event.source_engine == "json_engine" and event.attributes.get("key")
                           else event.field_path),
                    path=event.field_path,
                    page=event.page, event_type=event.event_type,
                    offset_start=event.offset, source_timestamp=event.raw_timestamp,
                    derived_view="timeline",
                ), context=event.context or event.description,
                normalization_value=event.timestamp,
            )


class AnalysisResultCorrelationProvider:
    """Configurable composite adapter; it does not modify AnalysisResult or contracts."""

    DEFAULT_PROVIDERS: tuple[CorrelationSourceProvider, ...] = (
        HashCorrelationProvider(), MetadataCorrelationProvider(), IpCorrelationProvider(),
        ResolvedEntityCorrelationProvider(), TextCorrelationProvider(), OcrCorrelationProvider(),
        JsonCorrelationProvider(), TimelineCorrelationProvider(),
    )

    def __init__(
        self, providers: Sequence[CorrelationSourceProvider] | None = None,
        *, disabled: Iterable[str] = (),
    ) -> None:
        disabled_names = frozenset(disabled)
        configured = tuple(providers) if providers is not None else self.DEFAULT_PROVIDERS
        self.providers = tuple(item for item in configured if item.provider_name not in disabled_names)

    def provide_many(self, results: Iterable[AnalysisResult]) -> Iterable[CorrelationCandidate]:
        for result in results:
            file_info = result.file_info
            source_file = source_file_identity(
                display_name=file_info.name, path=file_info.path,
                sha256=getattr(result.hashes, "sha256", None),
                session_id=getattr(result.evidence_source, "evidence_id", None)
                if getattr(result, "evidence_source", None) is not None else None,
            )
            for provider in self.providers:
                yield from provider.provide(result, source_file)


def derived_from_extracted_artifact(
    artifact: ExtractedArtifact, *, source_file: SourceFileIdentity,
    derived_file: SourceFileIdentity,
):
    from app.correlation.v2.models import DerivedFromCandidate

    return DerivedFromCandidate(
        derived_file=derived_file,
        source_file=source_file,
        provenance=CorrelationProvenance(
            engine="binary_extraction", path=str(artifact.destination_path),
            offset_start=artifact.start_offset, offset_end=artifact.end_offset,
            source_sha256=artifact.source_sha256,
            extracted_sha256=artifact.extracted_sha256,
            extraction_method=artifact.extraction_method,
        ),
    )


def _entity_source_key(source: EntitySource) -> tuple[object, ...]:
    return (
        source.source_type.value, source.page if source.page is not None else -1,
        source.start if source.start is not None else -1,
        source.end if source.end is not None else -1, source.field_path or "",
    )


def _raw_for_source(
    result: AnalysisResult, normalized: str, raw_values: tuple[str, ...], source: EntitySource,
) -> str:
    for segment in _text_segments(result):
        if _segment_source_type(segment.source) is not source.source_type or segment.page != source.page:
            continue
        if source.start is not None and source.end is not None and 0 <= source.start <= source.end <= len(segment.text):
            return segment.text[source.start:source.end]
    return raw_values[0] if len(raw_values) == 1 else normalized


def _source_context(source: EntitySource, raw: str) -> str:
    return "".join((source.context_before, raw, source.context_after)).strip()


def _text_segments(result: AnalysisResult):
    for step in reversed(getattr(result, "processing_steps", ()) or ()):
        if step.code == "text_extraction" and step.value is not None:
            return tuple(getattr(step.value, "segments", ()) or ())
    return ()


def _segment_source_type(value: str) -> EntitySourceType:
    return EntitySourceType.OCR if value == "ocr" else EntitySourceType.NATIVE_TEXT


def _normalized_key(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "", value.casefold())


def _json_path_depth(path: str) -> int:
    return 1 + path.count(".") + path.count("[")

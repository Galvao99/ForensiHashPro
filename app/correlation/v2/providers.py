from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
import re
from typing import Protocol

from app.correlation.v2.identity import source_file_identity
from app.correlation.v2.identity import stable_digest
from app.correlation.v2.models import (
    CorrelationCandidate, CorrelationProvenance, DeclaredHashTargetCandidate,
    EntityType, SourceFileIdentity,
    SignatureTemporalBindingCandidate,
)
from app.entities.models import EntitySource, EntitySourceType
from app.entities.models import EntityType as ResolvedEntityType
from app.models import AnalysisResult
from app.models.extracted_artifact import ExtractedArtifact
from app.investigation.declared_hash import DeclaredHashExtractor
from app.investigation.investigation_context import InvestigationContext
from app.services.temporal_parser import TemporalParser


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
                    CorrelationProvenance(
                        engine="hash_engine", field=field, source_type="calculated_hash",
                        parsing_method="calculated_from_artifact_bytes",
                    ),
                    semantic_role="calculated_hash",
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
                        source_type=source.source_type.value,
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
    capabilities = frozenset({EntityType.TIMESTAMP, EntityType.FILENAME, EntityType.PRODUCER, EntityType.CREATOR})
    FIELD_TYPES = {
        "CreateDate": EntityType.TIMESTAMP, "ModifyDate": EntityType.TIMESTAMP,
        "FileName": EntityType.FILENAME, "SourceFile": EntityType.FILENAME,
        "Producer": EntityType.PRODUCER, "Creator": EntityType.CREATOR,
        "CreatorTool": EntityType.PRODUCER,
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
                    CorrelationProvenance(
                        engine="metadata_engine", source_type="metadata",
                        field=str(field), path=str(field), metadata_key=str(field),
                        xmp_namespace=str(field).split(":", 1)[0] if ":" in str(field) else None,
                        xmp_key=leaf if ":" in str(field) else None,
                    ),
                    semantic_role={
                        EntityType.PRODUCER: "producer",
                        EntityType.CREATOR: "creator",
                    }.get(entity_type),
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
                    source_type="structured_json", field=item.key, path=item.path,
                    json_path=item.path, parsing_method="structured_field",
                ), context=f"{item.key}: {raw}",
                semantic_role=(
                    "declared_hash" if entity_type in {EntityType.SHA256, EntityType.MD5}
                    else "contract_number" if _normalized_key(item.key) == "document_identifier"
                    else None
                ),
            )


class TimelineCorrelationProvider:
    provider_name = "timeline"
    capabilities = frozenset({EntityType.TIMESTAMP})

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        has_signature_collection = bool(
            getattr(getattr(result, "digital_signature", None), "signatures", ())
        )
        events = sorted(
            getattr(result, "timeline_events", ()) or (),
            key=lambda item: (item.timestamp or "", item.event_type, item.event_id),
        )
        for event in events:
            if event.temporal_status == "structural_only":
                continue
            if has_signature_collection and event.category == "signature":
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
                    derived_view="timeline", source_type=(
                        "structured_json" if event.source_engine == "json_engine"
                        else "trusted_timestamp" if event.event_type == "timestamp_token"
                        else "pdf_embedded_signature" if event.category == "signature"
                        else event.source_type
                    ),
                    object_id=(
                        "embedded_signature:singleton"
                        if event.category == "signature" else None
                    ),
                    raw_value=event.raw_timestamp, timestamp_precision=event.precision,
                    timezone_status=event.timezone_status,
                ), context=event.context or event.description,
                normalization_value=event.timestamp,
                semantic_role=_timeline_semantic_role(event),
            )


class SignatureCorrelationProvider:
    """Projects canonical SignatureRecord collections into temporal evidence."""

    provider_name = "signature"
    capabilities = frozenset({EntityType.TIMESTAMP})

    def __init__(self, parser: TemporalParser | None = None) -> None:
        self.parser = parser or TemporalParser()

    def provide(
        self, result: AnalysisResult, source_file: SourceFileIdentity,
    ) -> Iterable[CorrelationCandidate]:
        for values in self._candidate_groups(result, source_file):
            yield from values.values()

    def binding(
        self, result: AnalysisResult, source_file: SourceFileIdentity,
    ) -> SignatureTemporalBindingCandidate | None:
        values = self.bindings(result, source_file)
        return values[0] if len(values) == 1 else None

    def bindings(
        self, result: AnalysisResult, source_file: SourceFileIdentity,
    ) -> tuple[SignatureTemporalBindingCandidate, ...]:
        signature = getattr(result, "digital_signature", None)
        if signature is None or getattr(signature, "has_signature", None) is not True:
            return ()
        records = tuple(getattr(signature, "signatures", ()) or ())
        if records:
            candidates = self._candidate_groups(result, source_file)
            bindings = [
                binding for record, values in zip(records, candidates)
                if (binding := self._record_binding(record, values)) is not None
            ]
            return tuple(sorted(bindings, key=lambda item: item.signature_id))
        if getattr(signature, "signature_count", 0) != 1:
            return ()
        values = self._legacy_candidates(signature, source_file)
        required_roles = {
            "signer_declared_signing_time", "certificate_not_before",
            "certificate_not_after",
        }
        issuer = str(getattr(signature, "issuer", "") or "").strip()
        serial = str(getattr(signature, "serial_number", "") or "").strip()
        if not issuer or not serial or not required_roles.issubset(values):
            return ()
        signature_id = stable_digest(
            "signature", [source_file.stable_id, "embedded_signature:singleton"],
        )
        certificate_id = stable_digest(
            "certificate", [source_file.stable_id, issuer, serial],
        )
        return (SignatureTemporalBindingCandidate(
            signature_id, certificate_id,
            values["signer_declared_signing_time"],
            values["certificate_not_before"], values["certificate_not_after"],
            CorrelationProvenance(
                engine="digital_signature_engine", source_engine="pyhanko",
                source_type="pdf_embedded_signature",
                object_id="embedded_signature:singleton",
                parsing_method="single_embedded_signature",
            ),
        ),)

    def _candidate_groups(
        self, result: AnalysisResult, source_file: SourceFileIdentity,
    ) -> tuple[dict[str, CorrelationCandidate], ...]:
        signature = getattr(result, "digital_signature", None)
        if signature is None or getattr(signature, "has_signature", None) is not True:
            return ()
        records = tuple(getattr(signature, "signatures", ()) or ())
        if records:
            return tuple(self._record_candidates(record, source_file) for record in records)
        return (self._legacy_candidates(signature, source_file),)

    def _record_candidates(
        self, record, source_file: SourceFileIdentity,
    ) -> dict[str, CorrelationCandidate]:
        certificate = record.certificate
        definitions = (
            ("signing_time", record.signing_time, "signer_declared_signing_time"),
            ("valid_from", certificate.valid_from if certificate else None, "certificate_not_before"),
            ("valid_until", certificate.valid_until if certificate else None, "certificate_not_after"),
            ("trusted_timestamp", record.trusted_timestamp, "trusted_timestamp_time"),
        )
        return self._temporal_candidates(
            definitions, source_file, record.signature_id,
            record.locator.canonical,
            certificate.certificate_id if certificate else None,
            record.locator.object_number, record.locator.object_generation,
            record.locator.signed_revision,
        )

    def _legacy_candidates(
        self, signature, source_file: SourceFileIdentity,
    ) -> dict[str, CorrelationCandidate]:
        definitions = (
            ("signing_time", getattr(signature, "signing_time", None), "signer_declared_signing_time"),
            ("valid_from", getattr(signature, "valid_from", None), "certificate_not_before"),
            ("valid_until", getattr(signature, "valid_until", None), "certificate_not_after"),
            ("timestamp", getattr(signature, "timestamp", None), "trusted_timestamp_time"),
        )
        return self._temporal_candidates(
            definitions, source_file, None, "embedded_signature:singleton", None,
            None, None, None,
        )

    def _temporal_candidates(
        self, definitions, source_file: SourceFileIdentity,
        signature_id: str | None, locator: str, certificate_id: str | None,
        object_number: int | None, object_generation: int | None,
        signed_revision: int | None,
    ) -> dict[str, CorrelationCandidate]:
        candidates: dict[str, CorrelationCandidate] = {}
        for field, raw, role in definitions:
            parsed = self.parser.parse(raw)
            if parsed is None:
                continue
            candidates[role] = CorrelationCandidate(
                EntityType.TIMESTAMP, parsed.raw, source_file,
                CorrelationProvenance(
                    engine="digital_signature_engine", source_engine="pyhanko",
                    source_type=(
                        "trusted_timestamp" if role == "trusted_timestamp_time"
                        else "pdf_embedded_signature"
                    ),
                    field=field, path=field, raw_value=parsed.raw,
                    parsing_method="signature_result_adapter",
                    timestamp_precision=parsed.precision,
                    timezone_status=parsed.timezone_status,
                    object_id=locator,
                    object_number=object_number,
                    object_generation=object_generation,
                    block=signed_revision,
                    asset_id=signature_id,
                    embedded_id=certificate_id,
                ), normalization_value=parsed.normalized, semantic_role=role,
            )
        return candidates

    @staticmethod
    def _record_binding(record, values) -> SignatureTemporalBindingCandidate | None:
        certificate = record.certificate
        required = {
            "signer_declared_signing_time", "certificate_not_before",
            "certificate_not_after",
        }
        if certificate is None or not required.issubset(values):
            return None
        return SignatureTemporalBindingCandidate(
            record.signature_id, certificate.certificate_id,
            values["signer_declared_signing_time"],
            values["certificate_not_before"], values["certificate_not_after"],
            CorrelationProvenance(
                engine="digital_signature_engine", source_engine="pyhanko",
                source_type="pdf_embedded_signature",
                object_id=record.locator.canonical,
                object_number=record.locator.object_number,
                object_generation=record.locator.object_generation,
                block=record.locator.signed_revision,
                parsing_method="signature_record_v1",
                embedded_id=certificate.certificate_id,
            ),
        )


class DeclaredHashCorrelationProvider:
    """Adapts explicit declarations and unpromoted hash-like text separately."""

    provider_name = "declared_hash"
    capabilities = frozenset({EntityType.SHA256, EntityType.MD5})

    def __init__(self, extractor: DeclaredHashExtractor | None = None) -> None:
        self.extractor = extractor or DeclaredHashExtractor()

    def provide(self, result: AnalysisResult, source_file: SourceFileIdentity) -> Iterable[CorrelationCandidate]:
        evidence_ref = source_file.session_id or source_file.stable_id
        for segment in _text_segments(result):
            for item in self.extractor.extract_text(
                segment.text, evidence_ref=evidence_ref,
                filename=source_file.display_name, source_type=segment.source,
                page=segment.page,
            ):
                entity_type = _hash_entity_type(item.algorithm)
                if entity_type is None:
                    continue
                role = "declared_hash" if item.declared else "hash_like"
                yield CorrelationCandidate(
                    entity_type, item.value, source_file,
                    CorrelationProvenance(
                        engine="declared_hash_extractor", source_type=item.source_type,
                        page=item.page, start=item.start, end=item.end,
                        raw_value=item.value, parsing_method=item.extractor,
                    ), context=item.context, semantic_role=role,
                )


class InvestigationContextCorrelationProvider:
    """Compatibility adapter for facts that only exist in the legacy Case context."""

    def provide_many(
        self, context: InvestigationContext, results: Iterable[AnalysisResult],
    ) -> Iterable[CorrelationCandidate]:
        files = _context_files(results)
        for role, fact_type, values in (
            ("producer", EntityType.PRODUCER, context.producers),
            ("creator", EntityType.CREATOR, context.creators),
        ):
            for key, raw in sorted(values.items()):
                source_file = _source_for_context_key(key, context, files)
                yield CorrelationCandidate(
                    fact_type, raw, source_file,
                    CorrelationProvenance(
                        engine="metadata_engine", source_type="metadata",
                        field=role, metadata_key=role,
                    ), semantic_role=role,
                )
        for key, values in sorted(context.declared_hashes.items()):
            source_file = _source_for_context_key(key, context, files)
            for item in values:
                fact_type = _hash_entity_type(item.algorithm)
                if fact_type is None:
                    continue
                role = "declared_hash" if item.declared else "hash_like"
                yield CorrelationCandidate(
                    fact_type, item.value, source_file,
                    CorrelationProvenance(
                        engine="declared_hash_extractor", source_type=item.source_type,
                        page=item.page, start=item.start, end=item.end,
                        path=item.field_path, raw_value=item.value,
                        parsing_method=item.extractor,
                    ), context=item.context, semantic_role=role,
                )


class AnalysisResultCorrelationProvider:
    """Configurable composite adapter; it does not modify AnalysisResult or contracts."""

    DEFAULT_PROVIDERS: tuple[CorrelationSourceProvider, ...] = (
        HashCorrelationProvider(), MetadataCorrelationProvider(), IpCorrelationProvider(),
        ResolvedEntityCorrelationProvider(), TextCorrelationProvider(), OcrCorrelationProvider(),
        JsonCorrelationProvider(), DeclaredHashCorrelationProvider(),
        SignatureCorrelationProvider(), TimelineCorrelationProvider(),
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

    def provide_case(self, results: Iterable[AnalysisResult]) -> "CanonicalEvidenceBatch":
        """Materialize facts and parser-supported cross-artifact bindings."""
        materialized = tuple(results)
        candidates = tuple(self.provide_many(materialized))
        sources = _result_sources(materialized)
        signature_provider = next(
            (item for item in self.providers if isinstance(item, SignatureCorrelationProvider)),
            None,
        )
        return CanonicalEvidenceBatch(
            candidates=candidates,
            declared_hash_targets=tuple(
                self._json_hash_targets(materialized, candidates)
            ),
            signature_temporal_bindings=tuple(
                binding for result in materialized
                if signature_provider is not None
                for binding in signature_provider.bindings(
                    result, sources[id(result)],
                )
            ),
        )

    @staticmethod
    def _json_hash_targets(
        results: tuple[AnalysisResult, ...],
        candidates: tuple[CorrelationCandidate, ...],
    ) -> Iterable[DeclaredHashTargetCandidate]:
        sources = _result_sources(results)
        by_name: dict[str, list[SourceFileIdentity]] = {}
        for source in sources.values():
            by_name.setdefault(_exact_filename(source.display_name), []).append(source)
        declarations = {
            (item.source_file.stable_id, item.provenance.path, item.entity_type): item
            for item in candidates
            if item.semantic_role == "declared_hash"
            and item.provenance.engine == "json_engine"
        }
        for result in results:
            analysis = getattr(result, "json_analysis", None)
            if analysis is None or not getattr(analysis, "is_valid", False):
                continue
            source = sources[id(result)]
            grouped: dict[str, list[object]] = {}
            for field in getattr(analysis, "fields", ()) or ():
                grouped.setdefault(_json_parent(field.path), []).append(field)
            for parent, fields in sorted(grouped.items()):
                filenames = [
                    field for field in fields
                    if _normalized_key(field.key) in {"filename", "file_name"}
                    and isinstance(field.value, str) and field.value.strip()
                ]
                hashes = [
                    field for field in fields
                    if _normalized_key(field.key) in {"sha256", "sha_256", "md5"}
                ]
                if len(filenames) != 1:
                    continue
                targets = [
                    target for target in by_name.get(_exact_filename(filenames[0].value), ())
                    if target.stable_id != source.stable_id
                ]
                if len(targets) != 1:
                    continue
                for field in hashes:
                    fact_type = (
                        EntityType.MD5 if _normalized_key(field.key) == "md5"
                        else EntityType.SHA256
                    )
                    declaration = declarations.get((source.stable_id, field.path, fact_type))
                    if declaration is None:
                        continue
                    yield DeclaredHashTargetCandidate(
                        declaration=declaration,
                        target_file=targets[0],
                        provenance=CorrelationProvenance(
                            engine="json_parser", source_type="structured_json",
                            field=f"{filenames[0].key}+{field.key}", path=parent,
                            json_path=parent, parsing_method="sibling_fields_exact_filename",
                            raw_value=filenames[0].value,
                        ),
                    )


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceBatch:
    candidates: tuple[CorrelationCandidate, ...] = ()
    declared_hash_targets: tuple[DeclaredHashTargetCandidate, ...] = ()
    signature_temporal_bindings: tuple[SignatureTemporalBindingCandidate, ...] = ()


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


def _hash_entity_type(algorithm: str) -> EntityType | None:
    return {"SHA-256": EntityType.SHA256, "MD5": EntityType.MD5}.get(algorithm.upper())


def _context_files(results: Iterable[AnalysisResult]) -> dict[str, SourceFileIdentity]:
    files: dict[str, SourceFileIdentity] = {}
    for result in results:
        source = source_file_identity(
            display_name=result.file_info.name, path=result.file_info.path,
            sha256=getattr(result.hashes, "sha256", None),
            session_id=(result.evidence_source.evidence_id if result.evidence_source else None),
        )
        files[result.file_info.name] = source
        files[str(result.file_info.path)] = source
        files[str(result.file_info.path.resolve())] = source
    return files


def _source_for_context_key(
    key: str, context: InvestigationContext, files: dict[str, SourceFileIdentity],
) -> SourceFileIdentity:
    source = files.get(key) or files.get(context.display_name_for(key))
    if source is not None:
        return source
    return source_file_identity(display_name=context.display_name_for(key), path=key)


def _result_sources(
    results: Iterable[AnalysisResult],
) -> dict[int, SourceFileIdentity]:
    return {
        id(result): source_file_identity(
            display_name=result.file_info.name, path=result.file_info.path,
            sha256=getattr(result.hashes, "sha256", None),
            session_id=(result.evidence_source.evidence_id if result.evidence_source else None),
        )
        for result in results
    }


def _exact_filename(value: str) -> str:
    return str(value).strip().replace("\\", "/").rsplit("/", 1)[-1].casefold()


def _json_parent(path: str) -> str:
    normalized = str(path).strip()
    return normalized.rsplit(".", 1)[0] if "." in normalized else "$"


def _timeline_semantic_role(event) -> str | None:
    if event.event_type == "signature":
        return "signer_declared_signing_time"
    if event.event_type == "timestamp_token":
        return "trusted_timestamp_time"
    if event.event_type == "certificate_validity":
        return {
            "valid_from": "certificate_not_before",
            "valid_until": "certificate_not_after",
        }.get(event.field_path)
    return None

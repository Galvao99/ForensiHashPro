from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EntityType(str, Enum):
    SHA256 = "sha256"
    MD5 = "md5"
    IP = "ip"
    EMAIL = "email"
    PHONE = "phone"
    CPF = "cpf"
    CNPJ = "cnpj"
    URL = "url"
    TIMESTAMP = "timestamp"
    FILENAME = "filename"
    DOCUMENT_IDENTIFIER = "document_identifier"
    PRODUCER = "producer"
    CREATOR = "creator"


class RelationType(str, Enum):
    ENTITY_OCCURS_IN_FILE = "ENTITY_OCCURS_IN_FILE"
    SAME_ENTITY_ACROSS_FILES = "SAME_ENTITY_ACROSS_FILES"
    SAME_HASH = "SAME_HASH"
    DERIVED_FROM = "DERIVED_FROM"
    OCCURRENCE_NORMALIZES_TO_FACT = "OCCURRENCE_NORMALIZES_TO_FACT"
    STRUCTURED_ASSOCIATION = "STRUCTURED_ASSOCIATION"


NORMALIZATION_VERSION = "1"


@dataclass(frozen=True, slots=True)
class SourceFileIdentity:
    stable_id: str
    display_name: str
    sha256: str | None = None
    path: str | None = None
    session_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrelationProvenance:
    engine: str
    source_engine: str | None = None
    field: str | None = None
    path: str | None = None
    page: int | None = None
    block: int | str | None = None
    bbox: tuple[float, float, float, float] | None = None
    event_type: str | None = None
    derived_view: str | None = None
    object_id: str | None = None
    object_number: int | None = None
    object_generation: int | None = None
    stream_id: str | None = None
    segment: str | None = None
    marker: str | None = None
    absolute_offset: int | None = None
    offset_start: int | None = None
    offset_end: int | None = None
    start: int | None = None
    end: int | None = None
    source_timestamp: str | None = None
    asset_id: str | None = None
    embedded_id: str | None = None
    source_sha256: str | None = None
    extracted_sha256: str | None = None
    extraction_method: str | None = None
    source_type: str | None = None
    raw_value: str | None = None
    parsing_method: str | None = None
    timestamp_precision: str | None = None
    timezone_status: str | None = None
    metadata_key: str | None = None
    json_path: str | None = None
    csv_row: int | None = None
    csv_column: str | None = None
    sql_context: str | None = None
    xmp_namespace: str | None = None
    xmp_key: str | None = None

    def __post_init__(self) -> None:
        if not self.engine.strip():
            raise ValueError("Provenance engine/source is required.")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def identity_dict(self) -> dict[str, Any]:
        """Primary coordinates; derived-view annotations do not create evidence."""
        value = self.to_dict()
        value.pop("event_type")
        value.pop("derived_view")
        value.pop("source_engine")
        for annotation in (
            "raw_value", "parsing_method", "timestamp_precision", "timezone_status",
            "metadata_key", "json_path", "xmp_namespace", "xmp_key",
        ):
            value.pop(annotation)
        if self.derived_view is not None:
            value["source_timestamp"] = None
        return value


@dataclass(frozen=True, slots=True)
class CorrelationOccurrence:
    occurrence_id: str
    entity_id: str
    entity_type: EntityType
    raw_value: str
    normalized_value: str
    source_file: SourceFileIdentity
    provenance: CorrelationProvenance
    context: str | None = None
    semantic_role: str | None = None
    normalization_version: str = NORMALIZATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["entity_type"] = self.entity_type.value
        return value


@dataclass(frozen=True, slots=True)
class CorrelationEntity:
    stable_id: str
    entity_type: EntityType
    normalized_value: str
    display_value: str
    occurrences: tuple[CorrelationOccurrence, ...]
    occurrence_count: int
    unique_file_count: int
    unique_source_count: int
    semantic_role: str | None = None
    normalization_version: str = NORMALIZATION_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "entity_type": self.entity_type.value,
            "normalized_value": self.normalized_value,
            "display_value": self.display_value,
            "occurrences": [item.to_dict() for item in self.occurrences],
            "occurrence_count": self.occurrence_count,
            "unique_file_count": self.unique_file_count,
            "unique_source_count": self.unique_source_count,
            "semantic_role": self.semantic_role,
            "normalization_version": self.normalization_version,
        }


@dataclass(frozen=True, slots=True)
class CorrelationRelation:
    stable_id: str
    relation_type: RelationType
    subject_id: str
    object_ids: tuple[str, ...]
    entity_id: str | None = None
    provenance: CorrelationProvenance | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "stable_id": self.stable_id,
            "relation_type": self.relation_type.value,
            "subject_id": self.subject_id,
            "object_ids": list(self.object_ids),
            "entity_id": self.entity_id,
            "provenance": self.provenance.to_dict() if self.provenance else None,
        }


@dataclass(frozen=True, slots=True)
class CorrelationSummary:
    total_entities: int
    total_occurrences: int
    total_relations: int
    entities_by_type: dict[str, int]
    cross_file_entities: int
    files_involved: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CorrelationReport:
    entities: tuple[CorrelationEntity, ...] = ()
    relations: tuple[CorrelationRelation, ...] = ()
    summary: CorrelationSummary = field(
        default_factory=lambda: CorrelationSummary(0, 0, 0, {}, 0, 0)
    )
    limitations: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entities": [item.to_dict() for item in self.entities],
            "relations": [item.to_dict() for item in self.relations],
            "summary": self.summary.to_dict(),
            "limitations": list(self.limitations),
        }


@dataclass(frozen=True, slots=True)
class CorrelationCandidate:
    entity_type: EntityType
    raw_value: str
    source_file: SourceFileIdentity
    provenance: CorrelationProvenance
    context: str | None = None
    normalization_value: str | None = None
    semantic_role: str | None = None
    normalization_version: str = NORMALIZATION_VERSION


@dataclass(frozen=True, slots=True)
class DerivedFromCandidate:
    derived_file: SourceFileIdentity
    source_file: SourceFileIdentity
    provenance: CorrelationProvenance


@dataclass(frozen=True, slots=True)
class StructuredRelationCandidate:
    relation_type: RelationType
    subject_id: str
    object_ids: tuple[str, ...]
    provenance: CorrelationProvenance

    def __post_init__(self) -> None:
        if self.relation_type is not RelationType.STRUCTURED_ASSOCIATION:
            raise ValueError("Explicit parser relations must use STRUCTURED_ASSOCIATION.")
        if not self.subject_id or not self.object_ids:
            raise ValueError("Structured relation endpoints are required.")


# Canonical terminology. The V2 names remain public compatibility aliases.
CanonicalFact = CorrelationEntity
CanonicalOccurrence = CorrelationOccurrence
CanonicalProvenance = CorrelationProvenance


def display_filename(path: str | Path) -> str:
    return Path(path).name

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class EntityType(str, Enum):
    CPF = "cpf"
    PHONE = "phone"
    IP = "ip"
    MONEY = "money"
    DATETIME = "datetime"
    EMAIL = "email"
    UNKNOWN_NUMERIC_IDENTIFIER = "unknown_numeric_identifier"
    AMBIGUOUS = "ambiguous"


class EntitySourceType(str, Enum):
    NATIVE_TEXT = "native_text"
    OCR = "ocr"
    METADATA = "metadata"
    JSON = "json"
    STRUCTURED = "structured"
    LEGACY_TEXT = "legacy_text"


@dataclass(frozen=True, slots=True)
class EntitySource:
    source_type: EntitySourceType
    source_file: str
    page: int | None = None
    start: int | None = None
    end: int | None = None
    context_before: str = ""
    context_after: str = ""
    extractor: str = ""
    field_path: str | None = None

    @property
    def context(self) -> str:
        return " ".join(
            part.strip()
            for part in (self.context_before, self.context_after)
            if part.strip()
        )


@dataclass(frozen=True, slots=True)
class EntityCandidate:
    raw_value: str
    normalized_candidate: str
    source: EntitySource
    initial_hints: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ValidationResult:
    entity_type: EntityType
    valid: bool
    normalized_value: str | None = None
    structural_confidence: float = 0.0
    formatting_confidence: float = 0.0
    attributes: dict[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ConfidenceComponent:
    component: str
    value: float
    reason: str


@dataclass(frozen=True, slots=True)
class EntityHypothesis:
    entity_type: EntityType
    normalized_value: str
    confidence: float
    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NormalizedEntity:
    entity_type: EntityType
    normalized_value: str
    confidence: float
    raw_values: tuple[str, ...]
    sources: tuple[EntitySource, ...]
    confidence_components: tuple[ConfidenceComponent, ...] = ()
    attributes: dict[str, Any] = field(default_factory=dict)
    hypotheses: tuple[EntityHypothesis, ...] = ()


@dataclass(frozen=True, slots=True)
class EntityResolutionResult:
    candidates: tuple[EntityCandidate, ...]
    entities: tuple[NormalizedEntity, ...]


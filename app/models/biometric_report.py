from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class ConstraintEvaluationStatus(str, Enum):
    BELOW_MINIMUM = "BELOW_MINIMUM"
    WITHIN_RANGE = "WITHIN_RANGE"
    PREFERRED = "PREFERRED"
    ABOVE_MAXIMUM = "ABOVE_MAXIMUM"
    NOT_EVALUATED = "NOT_EVALUATED"


@dataclass(slots=True)
class BiometricMetric:
    original_name: str
    value: Any
    canonical_name: str | None = None
    original_value: Any = None
    original_unit: str | None = None
    canonical_unit: str | None = None
    category: str | None = None
    original_category: str | None = None
    source_path: str = ""
    raw_data: Any = None

    def __post_init__(self) -> None:
        if self.original_value is None:
            self.original_value = self.value


@dataclass(slots=True)
class BiometricDecision:
    original_name: str
    value: Any
    canonical_name: str | None = None
    original_value: Any = None
    category: str | None = None
    source_path: str = ""
    raw_data: Any = None

    def __post_init__(self) -> None:
        if self.original_value is None:
            self.original_value = self.value


@dataclass(slots=True)
class BiometricAlgorithmResult:
    original_name: str
    value: Any = None
    canonical_name: str | None = None
    original_value: Any = None
    version: str | None = None
    unit: str | None = None
    category: str | None = None
    source_path: str = ""
    metrics: list[BiometricMetric] = field(default_factory=list)
    raw_data: Any = None

    def __post_init__(self) -> None:
        if self.original_value is None:
            self.original_value = self.value


@dataclass(slots=True)
class BiometricConstraint:
    original_name: str
    canonical_name: str | None = None
    minimum: float | None = None
    preferred: float | None = None
    maximum: float | None = None
    original_unit: str | None = None
    canonical_unit: str | None = None
    source_path: str = ""
    raw_data: Any = None


@dataclass(slots=True)
class BiometricConstraintEvaluation:
    metric: BiometricMetric
    constraint: BiometricConstraint
    observed_value: Any
    unit: str | None
    status: ConstraintEvaluationStatus
    justification: str
    tolerance: float | None = None


@dataclass(slots=True)
class BiometricEvidence:
    evidence_type: str
    original_reference: str
    resolved_path: Path | None = None
    exists: bool | None = None
    file_name: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = None
    hashes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_path: str = ""
    raw_data: Any = None


@dataclass(slots=True)
class BiometricReport:
    provider: str | None = None
    product: str | None = None
    version: str | None = None
    workflow: str | None = None
    analysis_date: datetime | None = None
    timestamps: dict[str, datetime | str] = field(default_factory=dict)
    decisions: list[BiometricDecision] = field(default_factory=list)
    algorithms: list[BiometricAlgorithmResult] = field(default_factory=list)
    metrics: list[BiometricMetric] = field(default_factory=list)
    constraints: list[BiometricConstraint] = field(default_factory=list)
    constraint_evaluations: list[BiometricConstraintEvaluation] = field(
        default_factory=list
    )
    evidences: list[BiometricEvidence] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    has_profile: bool = False
    raw_payload: Any = None


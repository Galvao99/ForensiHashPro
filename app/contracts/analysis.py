from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


SCHEMA_VERSION = "1.0.0"


class AnalysisState(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPROMISED = "compromised"


class ProgressStatus(str, Enum):
    STARTED = "started"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class Fact:
    fact_id: str
    kind: str
    source: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FindingContract:
    finding_id: str
    rule_id: str
    severity: str
    title: str
    statement: str
    evidence_refs: list[str] = field(default_factory=list)
    recommendation: str | None = None
    confidence: float | None = None


@dataclass(frozen=True, slots=True)
class Limitation:
    limitation_id: str
    code: str
    component: str
    message: str
    impact: str


@dataclass(frozen=True, slots=True)
class ContractError:
    error_id: str
    code: str
    component: str
    message: str
    impact: str
    occurred_at: datetime
    safe_details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExternalResult:
    result_id: str
    provider: str
    kind: str
    observed_at: datetime
    data: dict[str, Any] = field(default_factory=dict)
    limitations: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ProgressEvent:
    event_id: str
    analysis_id: str
    step: str
    status: ProgressStatus
    message: str
    occurred_at: datetime
    percentage: int | None = None


@dataclass(frozen=True, slots=True)
class AnalysisContract:
    schema_version: str
    analysis_id: str
    evidence_id: str
    state: AnalysisState
    file: dict[str, Any]
    hashes: dict[str, str]
    declared_type: str | None
    detected_type: str | None
    metadata: dict[str, Any] = field(default_factory=dict)
    technical_structure: dict[str, Any] = field(default_factory=dict)
    native_text: dict[str, Any] | None = None
    ocr: dict[str, Any] | None = None
    signatures: list[dict[str, Any]] = field(default_factory=list)
    ip_addresses: list[dict[str, Any]] = field(default_factory=list)
    timeline: list[dict[str, Any]] = field(default_factory=list)
    comparison: dict[str, Any] | None = None
    biometrics: dict[str, Any] | None = None
    facts: list[Fact] = field(default_factory=list)
    findings: list[FindingContract] = field(default_factory=list)
    limitations: list[Limitation] = field(default_factory=list)
    errors: list[ContractError] = field(default_factory=list)
    external_results: list[ExternalResult] = field(default_factory=list)
    processing_steps: list[dict[str, Any]] = field(default_factory=list)
    execution: dict[str, Any] = field(default_factory=dict)


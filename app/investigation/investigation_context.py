from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models import AnalysisResult
from app.models.detected_ip import DetectedIp
from app.models.json_analysis_result import (
    JsonAnalysisResult,
)
from app.entities.models import NormalizedEntity
from app.investigation.declared_hash import DeclaredHashOccurrence


@dataclass(slots=True)
class InvestigationContext:
    """
    Contexto consolidado utilizado pelas regras investigativas.
    """

    results: list[AnalysisResult] = field(
        default_factory=list
    )

    display_names: dict[str, str] = field(
        default_factory=dict
    )

    extracted_texts: dict[str, str] = field(
        default_factory=dict
    )

    resolved_entities: dict[str, list[NormalizedEntity]] = field(
        default_factory=dict
    )

    calculated_hashes: dict[
        str,
        dict[str, str],
    ] = field(default_factory=dict)

    declared_hashes: dict[str, list[DeclaredHashOccurrence]] = field(default_factory=dict)

    contract_dates: dict[str, datetime] = field(
        default_factory=dict
    )

    metadata_dates: dict[
        str,
        dict[str, datetime],
    ] = field(default_factory=dict)

    metadata_values: dict[
        str,
        dict[str, Any],
    ] = field(default_factory=dict)

    producers: dict[str, str] = field(
        default_factory=dict
    )

    creators: dict[str, str] = field(
        default_factory=dict
    )

    detected_ips: dict[
        str,
        list[str],
    ] = field(default_factory=dict)

    detected_ip_details: dict[
        str,
        list[DetectedIp]
    ] = field(default_factory=dict)

    ip_results: dict[
        str,
        list[Any],
    ] = field(default_factory=dict)

    signature_results: dict[
        str,
        Any,
    ] = field(default_factory=dict)

    timeline_events: dict[
        str,
        list[Any],
    ] = field(default_factory=dict)

    json_results: dict[
        str,
        JsonAnalysisResult,
    ] = field(default_factory=dict)

    raw: dict[str, Any] = field(
        default_factory=dict
    )

    def display_name_for(
        self,
        evidence_key: str,
    ) -> str:
        return self.display_names.get(
            evidence_key,
            evidence_key,
        )

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models import AnalysisResult


@dataclass(slots=True)
class InvestigationContext:
    """
    Contexto consolidado para regras investigativas.

    A ideia é evitar que cada regra precise ficar procurando dados
    diretamente dentro do AnalysisResult.
    """

    results: list[AnalysisResult] = field(default_factory=list)

    extracted_texts: dict[str, str] = field(default_factory=dict)
    calculated_hashes: dict[str, dict[str, str]] = field(default_factory=dict)
    contract_dates: dict[str, datetime] = field(default_factory=dict)
    metadata_dates: dict[str, dict[str, datetime]] = field(default_factory=dict)

    raw: dict[str, Any] = field(default_factory=dict)
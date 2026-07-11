from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.models import AnalysisResult


@dataclass(slots=True)
class InvestigationContext:
    """
    Contexto consolidado utilizado pelas regras investigativas.

    Centraliza os resultados técnicos para evitar que cada regra
    precise navegar diretamente pela estrutura de AnalysisResult.
    """

    # Resultados originais das análises
    results: list[AnalysisResult] = field(default_factory=list)

    # Texto extraído por arquivo
    extracted_texts: dict[str, str] = field(default_factory=dict)

    # Hashes calculados por arquivo
    calculated_hashes: dict[str, dict[str, str]] = field(
        default_factory=dict
    )

    # Data contratual extraída por arquivo
    contract_dates: dict[str, datetime] = field(
        default_factory=dict
    )

    # Datas obtidas dos metadados
    metadata_dates: dict[str, dict[str, datetime]] = field(
        default_factory=dict
    )

    # Metadados gerais por arquivo
    metadata_values: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )

    # Producer identificado por arquivo
    producers: dict[str, str] = field(
        default_factory=dict
    )

    # Creator identificado por arquivo
    creators: dict[str, str] = field(
        default_factory=dict
    )

    # Endereços IP encontrados por arquivo
    detected_ips: dict[str, list[str]] = field(
        default_factory=dict
    )

    # Informações enriquecidas dos IPs
    ip_results: dict[str, list[Any]] = field(
        default_factory=dict
    )

    # Informações sobre assinaturas digitais
    signature_results: dict[str, Any] = field(
        default_factory=dict
    )

    # Eventos técnicos utilizados pela timeline
    timeline_events: dict[str, list[Any]] = field(
        default_factory=dict
    )

    # Dados adicionais que ainda não possuem campo específico
    raw: dict[str, Any] = field(default_factory=dict)
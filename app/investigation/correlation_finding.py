from dataclasses import dataclass, field
from typing import Any

from app.models.badge import Badge


@dataclass(frozen=True, slots=True)
class CorrelationEvidence:
    evidence_ref: str
    filename: str
    role: str | None = None
    source_type: str | None = None
    page: int | None = None
    start: int | None = None
    end: int | None = None
    field_path: str | None = None
    context: str = ""
    raw_value: str | None = None
    normalized_value: str | None = None
    extractor: str | None = None


@dataclass(frozen=True, slots=True)
class CorrelationEntityRef:
    entity_type: str
    normalized_value: str
    confidence: float
    role: str | None = None


@dataclass(slots=True)
class CorrelationFinding:
    """
    Representa uma evidência técnica identificada durante
    a investigação dos arquivos analisados.

    Cada Finding deve representar uma única evidência,
    independente da regra que a originou.
    """

    # Identificação
    title: str
    description: str

    # Severidade
    severity: str = "info"  # info | ok | warning | critical

    # Regra responsável
    rule_id: str = ""

    # UI
    icon: str = ""

    # Arquivos relacionados
    source_file: str | None = None
    target_file: str | None = None

    # Identidade interna da evidência. Nesta fase transitória,
    # contém o caminho absoluto normalizado; futuramente poderá
    # receber diretamente o identificador da entidade Evidence.
    source_evidence_key: str | None = None
    target_evidence_key: str | None = None

    # Ordem de exibição na interface
    priority: int = 100

    # Badges visuais
    badges: list[Badge] = field(default_factory=list)

    # Dados técnicos completos
    metadata: dict[str, Any] = field(default_factory=dict)

    # Extensão V2. Todos os campos possuem defaults para preservar os
    # construtores e widgets legados.
    finding_id: str = ""
    category: str = "correlation"
    evidence: list[CorrelationEvidence] = field(default_factory=list)
    entities: list[CorrelationEntityRef] = field(default_factory=list)
    source_engine: str = "correlation_engine_v2"
    confidence: float | None = None
    limitations: list[str] = field(default_factory=list)

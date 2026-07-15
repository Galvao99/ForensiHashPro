from dataclasses import dataclass, field
from typing import Any

from app.models.badge import Badge


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

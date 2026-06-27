from abc import ABC, abstractmethod

from app.models import Finding, MetadataResult


class MetadataRule(ABC):
    """Contrato base para regras de análise de metadados."""

    @abstractmethod
    def apply(self, metadata: MetadataResult) -> list[Finding]:
        """Aplica a regra e retorna achados periciais."""
        pass
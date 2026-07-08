from abc import ABC, abstractmethod

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext


class BaseCorrelationRule(ABC):
    rule_id: str = "base"
    name: str = "Regra base"

    @abstractmethod
    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        raise NotImplementedError
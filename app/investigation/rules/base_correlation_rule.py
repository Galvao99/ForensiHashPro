from abc import ABC, abstractmethod
from typing import Sequence

from app.investigation.correlation_finding import CorrelationFinding
from app.models import AnalysisResult


class BaseCorrelationRule(ABC):
    rule_id: str = "base"
    name: str = "Regra base"

    @abstractmethod
    def evaluate(
        self,
        results: Sequence[AnalysisResult],
    ) -> list[CorrelationFinding]:
        raise NotImplementedError
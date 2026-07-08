from typing import Sequence

from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.correlation_result import CorrelationResult
from app.investigation.rules import MetadataContractDateRule
from app.models import AnalysisResult


class CorrelationService:
    """
    Serviço responsável por executar as regras de correlação investigativa
    sobre um ou mais resultados de análise.
    """

    def __init__(self) -> None:
        self.engine = CorrelationEngine(
            rules=[
                MetadataContractDateRule(),
            ]
        )

    def analyze(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        return self.engine.evaluate(results)
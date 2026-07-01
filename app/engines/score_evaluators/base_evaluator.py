from abc import ABC, abstractmethod

from app.models import AnalysisResult, ScoreSection


class BaseScoreEvaluator(ABC):
    """Contrato base para avaliadores de score."""

    @abstractmethod
    def evaluate(self, result: AnalysisResult) -> ScoreSection:
        pass
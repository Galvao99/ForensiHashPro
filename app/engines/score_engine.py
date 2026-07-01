from app.engines.score_evaluators.magic_number_evaluator import MagicNumberEvaluator
from app.engines.score_evaluators.metadata_evaluator import MetadataEvaluator
from app.engines.score_evaluators.signature_evaluator import SignatureEvaluator
from app.models import AnalysisResult, ScoreResult, ScoreSection
from app.engines.score_evaluators.findings_evaluator import FindingsEvaluator


class ScoreEngine:
    """
    Consolida o score pericial.

    O hash não entra no score global.
    Ele serve como fingerprint e para comparação/cadeia de custódia.
    """

    def __init__(self) -> None:
        self.evaluators = [
            MagicNumberEvaluator(),
            SignatureEvaluator(),
            MetadataEvaluator(),
            FindingsEvaluator(),
        ]

    def calculate(self, result: AnalysisResult) -> ScoreResult:
        sections = [
            evaluator.evaluate(result)
            for evaluator in self.evaluators
        ]

        final_score = self._calculate_weighted_score(sections)

        return ScoreResult(
            score=final_score,
            risk_level=self._risk_level(final_score),
            confidence_level=self._confidence_level(final_score),
            sections=sections,
        )

    def _calculate_weighted_score(self, sections: list[ScoreSection]) -> int:
        total_weight = sum(section.weight for section in sections)

        if total_weight == 0:
            return 0

        weighted_sum = sum(
            section.score * section.weight
            for section in sections
        )

        return int(weighted_sum / total_weight)

    def _risk_level(self, score: int) -> str:
        if score >= 85:
            return "Baixo"
        if score >= 65:
            return "Médio"
        return "Alto"

    def _confidence_level(self, score: int) -> str:
        if score >= 85:
            return "Alta"
        if score >= 65:
            return "Moderada"
        return "Baixa"
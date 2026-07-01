from app.config.score_weights import MAGIC_WEIGHT
from app.models import AnalysisResult, ScoreSection
from app.engines.score_evaluators.base_evaluator import BaseScoreEvaluator


class MagicNumberEvaluator(BaseScoreEvaluator):
    """Avalia a coerência entre extensão e assinatura binária."""

    def evaluate(self, result: AnalysisResult) -> ScoreSection:
        magic = result.magic_numbers

        exists = magic.detected_type != "Desconhecido"

        if not exists:
            return ScoreSection(
                name="Magic Number",
                exists=False,
                score=0,
                weight=MAGIC_WEIGHT,
                description="Não foi possível identificar a assinatura binária do arquivo.",
                details=[
                    f"Assinatura observada: {magic.signature}",
                ],
            )

        if magic.extension_matches:
            return ScoreSection(
                name="Magic Number",
                exists=True,
                score=100,
                weight=MAGIC_WEIGHT,
                description="A assinatura binária é compatível com a extensão declarada.",
                details=[
                    f"Tipo detectado: {magic.detected_type}",
                    f"Assinatura binária: {magic.signature}",
                ],
            )

        return ScoreSection(
            name="Magic Number",
            exists=True,
            score=20,
            weight=MAGIC_WEIGHT,
            description="A assinatura binária não é compatível com a extensão declarada.",
            details=[
                f"Tipo detectado: {magic.detected_type}",
                f"Extensão informada: {result.file_info.extension}",
                f"Assinatura binária: {magic.signature}",
            ],
        )
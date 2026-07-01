from app.config.score_weights import FINDINGS_WEIGHT
from app.enum.severity import Severity
from app.models import AnalysisResult, ScoreSection
from app.engines.score_evaluators.base_evaluator import BaseScoreEvaluator


class FindingsEvaluator(BaseScoreEvaluator):
    """Avalia o impacto dos vestígios técnicos no score."""

    def evaluate(self, result: AnalysisResult) -> ScoreSection:
        findings = result.findings or []

        if not findings:
            return ScoreSection(
                name="Vestígios",
                exists=True,
                score=100,
                weight=FINDINGS_WEIGHT,
                description="Nenhum vestígio técnico relevante foi identificado.",
                details=[
                    "Não foram encontrados indícios automáticos de reprocessamento, edição ou inconsistência nos critérios atualmente avaliados."
                ],
            )

        penalty = 0
        details = []

        for finding in findings:
            if finding.severity == Severity.CRITICAL:
                penalty += 35
            elif finding.severity == Severity.WARNING:
                penalty += 20
            elif finding.severity == Severity.INFO:
                penalty += 5

            details.append(
                f"{finding.severity.value.upper()} | {finding.title}: {finding.description}"
            )

        score = max(0, 100 - penalty)

        return ScoreSection(
            name="Vestígios",
            exists=True,
            score=score,
            weight=FINDINGS_WEIGHT,
            description=(
                f"Foram identificados {len(findings)} vestígio(s) técnico(s). "
                "A pontuação considera a severidade dos achados e seu potencial impacto pericial."
            ),
            details=details[:6],
        )
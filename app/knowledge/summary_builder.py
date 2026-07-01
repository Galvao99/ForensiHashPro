from app.engines.score_engine import ScoreEngine
from app.models.analysis_result import AnalysisResult


class SummaryBuilder:
    """
    Monta o Resumo Pericial a partir do ScoreEngine.

    O SummaryBuilder não calcula score.
    Ele apenas apresenta o resultado consolidado.
    """

    def __init__(self):
        self.score_engine = ScoreEngine()

    def build(self, analysis_result: AnalysisResult) -> dict:
        score_result = self.score_engine.calculate(analysis_result)

        badges = []

        for section in score_result.sections:
            badges.append(
                self._badge(
                    f"{section.name}: {section.score}/100",
                    self._status_from_score(section.score),
                )
            )

        findings_text = [
            section.description
            for section in score_result.sections
        ]

        return {
            "title": "Resumo Pericial",
            "score": score_result.score,
            "risk_level": score_result.risk_level,
            "confidence_level": score_result.confidence_level,
            "badges": badges,
            "findings": findings_text,
            "insights": [],
            "expert_note": self._expert_note(score_result.score),
        }

    def _badge(self, label: str, status: str) -> dict:
        return {
            "label": label,
            "status": status,
        }

    def _status_from_score(self, score: int) -> str:
        if score >= 85:
            return "ok"
        if score >= 65:
            return "warning"
        return "danger"

    def _expert_note(self, score: int) -> str:
        if score >= 85:
            return (
                "Os elementos técnicos analisados apresentam boa consistência geral. "
                "O hash foi calculado para identificação do arquivo, mas não integra o score pericial isoladamente."
            )

        if score >= 65:
            return (
                "A análise identificou elementos que recomendam cautela interpretativa. "
                "O score deve ser analisado em conjunto com os vestígios técnicos e o contexto documental."
            )

        return (
            "A análise identificou limitações ou inconsistências relevantes. "
            "Recomenda-se revisão manual aprofundada e correlação com documentos originais, logs e demais elementos técnicos."
        )
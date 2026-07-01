from app.models import AnalysisResult
from app.models.evaluation_item import EvaluationItem


class IntegrityEngine:

    def evaluate(
        self,
        result: AnalysisResult,
    ) -> list[EvaluationItem]:

        items = []

        items.append(
            EvaluationItem(
                title="Hash SHA-256",
                passed=bool(result.hashes.sha256),
                description="Hash calculado com sucesso.",
            )
        )

        items.append(
            EvaluationItem(
                title="Magic Number",
                passed=result.magic_numbers.extension_matches,
                description=(
                    "Assinatura binária compatível com a extensão."
                ),
            )
        )

        items.append(
            EvaluationItem(
                title="Assinatura Digital",
                passed=result.digital_signature.has_signature,
                description=(
                    "Assinatura digital incorporada."
                    if result.digital_signature.has_signature
                    else "Nenhuma assinatura digital encontrada."
                ),
            )
        )

        return items

    def calculate_score(
        self,
        result: AnalysisResult,
    ) -> int:

        items = self.evaluate(result)

        approved = sum(
            item.passed
            for item in items
        )

        return int(
            approved
            / len(items)
            * 100
        )

    def build_status(
        self,
        result: AnalysisResult,
    ) -> str:

        score = self.calculate_score(result)

        if score >= 90:
            return (
                "Os elementos técnicos analisados indicam boa integridade estrutural."
            )

        if score >= 70:
            return (
                "A integridade estrutural aparenta estar preservada, embora existam pontos que recomendam análise complementar."
            )

        return (
            "Não foi possível atestar a integridade estrutural do arquivo."
        )
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
                    if result.digital_signature.has_signature is True
                    else "Nenhuma assinatura digital encontrada."
                    if result.digital_signature.has_signature is False
                    else result.digital_signature.technical_status
                ),
            )
        )

        return items

    def calculate_score(
        self,
        result: AnalysisResult,
    ) -> None:
        """Compatibilidade: o score agregado foi desativado."""
        return None

    def build_status(
        self,
        result: AnalysisResult,
    ) -> str:

        return (
            "Verificações registradas por dimensão; nenhuma conclusão agregada "
            "de integridade foi calculada."
        )

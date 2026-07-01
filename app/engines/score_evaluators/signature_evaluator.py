from app.config.score_weights import SIGNATURE_WEIGHT
from app.models import AnalysisResult, ScoreSection
from app.engines.score_evaluators.base_evaluator import BaseScoreEvaluator


class SignatureEvaluator(BaseScoreEvaluator):
    """Avalia a presença e riqueza técnica da assinatura digital."""

    def evaluate(self, result: AnalysisResult) -> ScoreSection:
        signature = result.digital_signature

        if not signature.has_signature:
            return ScoreSection(
                name="Assinatura Digital",
                exists=False,
                score=0,
                weight=SIGNATURE_WEIGHT,
                description=(
                    "Não foi identificada assinatura digital incorporada ao arquivo. "
                    "Isso não invalida o documento por si só, mas impede validação criptográfica independente."
                ),
                details=[
                    signature.technical_status,
                ],
            )

        points = 0
        details = []

        checks = [
            ("Assinante identificado", signature.signer),
            ("Emissor identificado", signature.issuer),
            ("Número serial identificado", signature.serial_number),
            ("Algoritmo identificado", signature.algorithm),
            ("Data de assinatura identificada", signature.signing_time),
            ("Validade inicial do certificado identificada", signature.valid_from),
            ("Validade final do certificado identificada", signature.valid_until),
        ]

        for label, value in checks:
            if value:
                points += 1
                details.append(f"✓ {label}: {value}")
            else:
                details.append(f"⚠ {label}: ausente")

        score = int((points / len(checks)) * 100)

        return ScoreSection(
            name="Assinatura Digital",
            exists=True,
            score=score,
            weight=SIGNATURE_WEIGHT,
            description="Foi identificada assinatura digital incorporada. A pontuação considera a riqueza dos dados extraídos.",
            details=details,
        )
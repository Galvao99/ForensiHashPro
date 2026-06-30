from app.enum.severity import Severity
from app.knowledge.insight_service import InsightService
from app.models.analysis_result import AnalysisResult


class SummaryBuilder:
    """
    Monta o Resumo Pericial a partir de um AnalysisResult.

    Este arquivo pertence à camada knowledge porque interpreta
    tecnicamente os resultados extraídos pelas engines.
    """

    def __init__(self):
        self.insight_service = InsightService()

    def build(self, analysis_result: AnalysisResult) -> dict:
        score = 100
        badges = []
        findings_text = []
        insights = []

        # HASH
        if analysis_result.hashes and analysis_result.hashes.sha256:
            badges.append(self._badge("Hash SHA-256 calculado", "ok"))
            findings_text.append(
                "Hash SHA-256 calculado para acautelamento e verificação de integridade do arquivo."
            )
        else:
            badges.append(self._badge("Hash não identificado", "warning"))
            findings_text.append(
                "Não foi identificado hash SHA-256 no resultado da análise."
            )
            score -= 20

        # MAGIC NUMBER
        magic_status = self._is_magic_valid(analysis_result)

        if magic_status is True:
            badges.append(self._badge("Magic Number compatível", "ok"))
            insights.append(self.insight_service.build_magic_number_insight(True))
        elif magic_status is False:
            badges.append(self._badge("Magic Number divergente", "danger"))
            findings_text.append(
                "Foi identificada possível divergência entre a extensão do arquivo e sua assinatura interna."
            )
            insights.append(self.insight_service.build_magic_number_insight(False))
            score -= 30
        else:
            badges.append(self._badge("Magic Number não verificado", "neutral"))
            insights.append(self.insight_service.build_magic_number_insight(None))
            score -= 5

        # PRODUCER
        producer = self._get_producer(analysis_result)

        if producer:
            badges.append(self._badge("Producer identificado", "info"))
            findings_text.append(f"Producer identificado nos metadados: {producer}.")
            insights.append(self.insight_service.build_producer_insight(producer))
        else:
            badges.append(self._badge("Producer ausente", "neutral"))
            insights.append(self.insight_service.build_producer_insight(None))
            score -= 5

        # ASSINATURA DIGITAL
        signature_status = self._has_digital_signature(analysis_result)

        if signature_status is True:
            badges.append(self._badge("Assinatura digital encontrada", "ok"))
            insights.append(self.insight_service.build_signature_insight(True))
        elif signature_status is False:
            badges.append(self._badge("Assinatura digital ausente", "warning"))
            insights.append(self.insight_service.build_signature_insight(False))
            score -= 10
        else:
            badges.append(self._badge("Assinatura não verificada", "neutral"))
            insights.append(self.insight_service.build_signature_insight(None))
            score -= 5

        # VESTÍGIOS
        findings = analysis_result.findings or []

        if findings:
            badges.append(self._badge(f"{len(findings)} vestígio(s) encontrado(s)", "warning"))
            findings_text.append(
                f"Foram identificados {len(findings)} vestígio(s) técnico(s) durante a análise."
            )

            score -= self._calculate_findings_penalty(findings)

            for finding in findings[:3]:
                findings_text.append(
                    f"{finding.title}: {finding.description}"
                )
        else:
            badges.append(self._badge("Sem vestígios críticos", "ok"))
            findings_text.append(
                "Não foram identificados vestígios críticos no resultado disponível."
            )

        score = max(0, min(score, 100))

        return {
            "title": "Resumo Pericial",
            "score": score,
            "risk_level": self._risk_level(score),
            "badges": badges,
            "findings": findings_text,
            "insights": insights,
            "expert_note": self._expert_note(score),
        }

    def _get_producer(self, analysis_result: AnalysisResult) -> str | None:
        metadata = analysis_result.metadata

        if not metadata:
            return None

        possible_keys = [
            "Producer",
            "producer",
            "PDF:Producer",
            "XMP:Producer",
            "Creator",
            "creator",
            "Software",
            "software",
        ]

        for key in possible_keys:
            value = metadata.get(key)
            if value:
                return str(value)

        return None

    def _is_magic_valid(self, analysis_result: AnalysisResult) -> bool | None:
        magic = analysis_result.magic_numbers

        if magic is None:
            return None

        possible_attrs = [
            "is_valid",
            "valid",
            "matches_extension",
            "is_compatible",
        ]

        for attr in possible_attrs:
            if hasattr(magic, attr):
                value = getattr(magic, attr)
                if isinstance(value, bool):
                    return value

        return None

    def _has_digital_signature(self, analysis_result: AnalysisResult) -> bool | None:
        signature = analysis_result.digital_signature

        if signature is None:
            return None

        possible_attrs = [
            "has_signature",
            "is_signed",
            "valid",
            "is_valid",
            "signature_found",
        ]

        for attr in possible_attrs:
            if hasattr(signature, attr):
                value = getattr(signature, attr)
                if isinstance(value, bool):
                    return value

        return None

    def _calculate_findings_penalty(self, findings) -> int:
        penalty = 0

        for finding in findings:
            if finding.severity == Severity.CRITICAL:
                penalty += 15
            elif finding.severity == Severity.WARNING:
                penalty += 8
            elif finding.severity == Severity.INFO:
                penalty += 2
            elif finding.severity == Severity.SUCCESS:
                penalty += 0
            else:
                penalty += 1

        return min(penalty, 25)

    def _badge(self, label: str, status: str) -> dict:
        return {
            "label": label,
            "status": status,
        }

    def _risk_level(self, score: int) -> str:
        if score >= 85:
            return "Baixo"
        if score >= 65:
            return "Médio"
        return "Alto"

    def _expert_note(self, score: int) -> str:
        if score >= 85:
            return (
                "Os elementos técnicos analisados apresentam boa consistência geral. "
                "Ainda assim, os achados devem ser interpretados em conjunto com o contexto documental e processual."
            )

        if score >= 65:
            return (
                "A análise identificou elementos que recomendam cautela interpretativa. "
                "Os vestígios encontrados não devem ser avaliados isoladamente, mas em conjunto com os demais dados técnicos."
            )

        return (
            "A análise identificou limitações ou inconsistências relevantes. "
            "Recomenda-se revisão manual aprofundada e correlação com documentos originais, logs e demais elementos técnicos."
        )
from app.enum.severity import Severity
from app.knowledge.findings.integrity import INTEGRITY_FINDINGS
from app.models import Finding
from app.models.integrity_result import IntegrityResult
from app.models.digital_signature_result import (
    SignatureAnalysisStatus,
)


class IntegrityRule:
    """Interpreta o resultado de integridade do arquivo."""

    def apply(self, integrity: IntegrityResult) -> list[Finding]:
        findings: list[Finding] = []

        if not integrity.hash_verified:
            findings.append(self._from_definition("missing_hash"))

        if not integrity.magic_number_verified:
            findings.append(
                Finding(
                    severity=Severity.WARNING,
                    category="Integridade",
                    title="Magic number não confirmado",
                    description=(
                        "A assinatura inicial do arquivo não foi confirmada ou não apresentou "
                        "correspondência segura com o tipo declarado. Esse elemento pode indicar "
                        "divergência entre extensão e conteúdo real, arquivo corrompido ou formato "
                        "não reconhecido pela versão atual do analisador."
                    ),
                    evidence_source="Magic Number",
                    observed_value="Não confirmado",
                    recommendation=(
                        "Conferir manualmente a assinatura hexadecimal inicial do arquivo e "
                        "comparar com o formato declarado pela extensão."
                    ),
                    score=0.75,
                )
            )

        if integrity.digital_signature_present is False:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="Assinatura Digital",
                    title="Assinatura digital não identificada",
                    description=(
                        "Não foi identificada assinatura digital incorporada ao arquivo analisado. "
                        "Esse fato não invalida automaticamente o documento, especialmente em fluxos "
                        "de assinatura eletrônica não baseados em certificado digital ICP-Brasil, mas "
                        "limita a verificação criptográfica direta da autoria e integridade."
                    ),
                    evidence_source="Assinatura Digital",
                    observed_value="Ausente",
                    recommendation=(
                        "Solicitar logs de contratação, trilha de auditoria, evidências de autenticação, "
                        "hashes de origem e demais registros técnicos do fluxo eletrônico."
                    ),
                    score=0.80,
                )
            )

        if (
            integrity.digital_signature_analysis_status
            == SignatureAnalysisStatus.ERROR
        ):
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="Assinatura Digital",
                    title=(
                        "Não foi possível analisar a assinatura digital"
                    ),
                    description=(
                        "A análise de assinatura digital não foi concluída. "
                        "Não é possível afirmar se há ou não assinatura incorporada. "
                        "Recomenda-se realizar uma nova análise ou verificar o documento."
                    ),
                    evidence_source="Assinatura Digital",
                    observed_value="Análise não concluída",
                    recommendation=(
                        "Repetir a análise e verificar a integridade estrutural "
                        "e a compatibilidade do documento PDF."
                    ),
                    score=0.80,
                )
            )

        return findings

    def _from_definition(self, key: str) -> Finding:
        definition = INTEGRITY_FINDINGS[key]

        return Finding(
            severity=self._map_severity(definition.severity.value),
            category=definition.category,
            title=definition.title,
            description=(
                f"{definition.explanation}\n\n"
                f"Natureza: {definition.nature}\n\n"
                f"Impacto pericial: {definition.forensic_impact}"
            ),
            evidence_source="Integridade",
            observed_value="Não verificado",
            recommendation=definition.recommendation,
            score=0.75,
        )

    def _map_severity(self, severity: str) -> Severity:
        if severity == "critical":
            return Severity.CRITICAL

        if severity == "warning":
            return Severity.WARNING

        return Severity.INFO

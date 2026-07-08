from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class IpContextRule(BaseCorrelationRule):
    rule_id = "ip_context"
    name = "Contexto técnico de IP"

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        ip_results = context.raw.get("ip_results", [])

        for ip_result in ip_results:
            ip = getattr(ip_result, "ip", "")

            if getattr(ip_result, "routable", True) is False:
                findings.append(
                    CorrelationFinding(
                        title="IP interno ou não roteável identificado",
                        message=(
                            f"O endereço IP '{ip}' é interno, privado, reservado ou não roteável "
                            "publicamente. Esse tipo de endereço limita a verificação externa da "
                            "origem da conexão e recomenda análise conjunta com logs internos, "
                            "NAT/CGNAT e registros da instituição."
                        ),
                        severity="warning",
                        rule_id=self.rule_id,
                        evidence={
                            "ip": ip,
                            "tipo": getattr(ip_result, "type", ""),
                            "roteavel": getattr(ip_result, "routable", None),
                            "observacoes": getattr(ip_result, "notes", []),
                        },
                    )
                )

            if getattr(ip_result, "is_proxy", False):
                findings.append(
                    CorrelationFinding(
                        title="Indício de proxy, VPN ou anonimização",
                        message=(
                            f"O endereço IP '{ip}' apresenta indicação de proxy, VPN, Tor, "
                            "data center ou mecanismo de anonimização, conforme retorno do provedor "
                            "de enriquecimento utilizado."
                        ),
                        severity="warning",
                        rule_id=self.rule_id,
                        evidence={
                            "ip": ip,
                            "provider": getattr(ip_result, "provider", ""),
                            "is_proxy": getattr(ip_result, "is_proxy", None),
                            "asn": getattr(ip_result, "asn", ""),
                            "isp": getattr(ip_result, "isp", ""),
                            "organization": getattr(ip_result, "organization", ""),
                        },
                    )
                )

            fraud_score = getattr(ip_result, "fraud_score", None)

            if isinstance(fraud_score, (int, float)) and fraud_score >= 70:
                findings.append(
                    CorrelationFinding(
                        title="IP com score de fraude elevado",
                        message=(
                            f"O endereço IP '{ip}' apresenta score de fraude elevado "
                            f"({fraud_score}). Esse achado recomenda cautela na interpretação "
                            "da origem do acesso."
                        ),
                        severity="warning",
                        rule_id=self.rule_id,
                        evidence={
                            "ip": ip,
                            "fraud_score": fraud_score,
                        },
                    )
                )

        return findings
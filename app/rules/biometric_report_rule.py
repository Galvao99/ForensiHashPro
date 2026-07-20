from app.enum.severity import Severity
from app.models import Finding
from app.models.biometric_report import (
    BiometricReport,
    ConstraintEvaluationStatus,
)


class BiometricReportRule:
    """Converte fatos biométricos canônicos em vestígios objetivos."""

    CATEGORY = "Biometria"
    SOURCE = "Relatório biométrico"

    def apply(self, report: BiometricReport) -> list[Finding]:
        findings = [
            self._finding(
                "Formato biométrico reconhecido",
                "Foi reconhecida uma estrutura de relatório biométrico suportada.",
            )
        ]
        self._append_declared_fields(findings, report)
        self._append_decisions(findings, report)
        self._append_profile(findings, report)
        self._append_evaluations(findings, report)
        self._append_limitations(findings, report)
        return findings

    def _append_declared_fields(
        self,
        findings: list[Finding],
        report: BiometricReport,
    ) -> None:
        for title, label, value in (
            ("Fornecedor declarado", "fornecedor", report.provider),
            ("Produto declarado", "produto", report.product),
            ("Workflow declarado", "workflow", report.workflow),
        ):
            if value:
                findings.append(
                    self._finding(
                        title,
                        f"O relatório declara o {label} '{value}'.",
                        observed_value=value,
                    )
                )

    def _append_decisions(
        self,
        findings: list[Finding],
        report: BiometricReport,
    ) -> None:
        for decision in report.decisions:
            findings.append(
                self._finding(
                    "Decisão declarada pelo fornecedor",
                    (
                        "O fornecedor registrou a decisão "
                        f"'{decision.original_name}' com o valor "
                        f"'{decision.value}'. O valor não constitui "
                        "verificação independente."
                    ),
                    observed_value=str(decision.value),
                )
            )

    def _append_profile(
        self,
        findings: list[Finding],
        report: BiometricReport,
    ) -> None:
        if report.has_profile:
            findings.append(
                self._finding(
                    "Perfil XML encontrado",
                    "Foi encontrado um perfil XML incorporado ao relatório.",
                )
            )
            findings.append(
                self._finding(
                    "Restrições de perfil encontradas",
                    (
                        "Foram encontradas "
                        f"{len(report.constraints)} restrição(ões) "
                        "interpretável(is) no perfil XML."
                    ),
                    observed_value=str(len(report.constraints)),
                )
            )
        else:
            findings.append(
                self._finding(
                    "Perfil XML ausente",
                    "Não foi encontrado perfil XML incorporado ao relatório.",
                )
            )

    def _append_evaluations(
        self,
        findings: list[Finding],
        report: BiometricReport,
    ) -> None:
        titles = {
            ConstraintEvaluationStatus.BELOW_MINIMUM: "Métrica abaixo do mínimo",
            ConstraintEvaluationStatus.ABOVE_MAXIMUM: "Métrica acima do máximo",
            ConstraintEvaluationStatus.NOT_EVALUATED: "Avaliação de métrica não realizada",
        }
        for evaluation in report.constraint_evaluations:
            title = titles.get(evaluation.status)
            if title is None:
                continue
            findings.append(
                self._finding(
                    title,
                    (
                        f"A métrica '{evaluation.metric.original_name}' "
                        f"foi classificada como {evaluation.status.value}. "
                        f"{evaluation.justification}"
                    ),
                    observed_value=str(evaluation.observed_value),
                )
            )

    def _append_limitations(
        self,
        findings: list[Finding],
        report: BiometricReport,
    ) -> None:
        if report.algorithms:
            findings.append(
                self._finding(
                    "Algoritmo proprietário não reproduzido",
                    (
                        "Foram encontrados resultados declarados de "
                        f"{len(report.algorithms)} algoritmo(s). Os algoritmos "
                        "proprietários não foram reproduzidos."
                    ),
                    observed_value=str(len(report.algorithms)),
                )
            )
        if report.decisions or report.algorithms:
            findings.append(
                self._finding(
                    "Validação independente limitada",
                    (
                        "Não foi possível verificar independentemente as "
                        "decisões ou os resultados algorítmicos apenas com "
                        "os dados disponibilizados no relatório."
                    ),
                )
            )

    def _finding(
        self,
        title: str,
        description: str,
        *,
        observed_value: str | None = None,
    ) -> Finding:
        return Finding(
            severity=Severity.INFO,
            category=self.CATEGORY,
            title=title,
            description=description,
            evidence_source=self.SOURCE,
            observed_value=observed_value,
        )

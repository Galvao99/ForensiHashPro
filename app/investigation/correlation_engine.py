from typing import Sequence

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models import AnalysisResult


class CorrelationEngine:
    def __init__(self, rules: list[BaseCorrelationRule]) -> None:
        self.rules = rules

    def evaluate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        correlation_result = CorrelationResult()

        for rule in self.rules:
            try:
                findings = rule.evaluate(results)

                for finding in findings:
                    correlation_result.add_finding(finding)

            except Exception as exc:
                correlation_result.add_finding(
                    CorrelationFinding(
                        title=f"Falha ao executar regra: {rule.name}",
                        message=str(exc),
                        severity="warning",
                        rule_id=rule.rule_id,
                    )
                )

        return correlation_result
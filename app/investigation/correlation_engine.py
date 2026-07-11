from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class CorrelationEngine:

    def __init__(
        self,
        rules: list[BaseCorrelationRule],
    ) -> None:

        self.rules = rules

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> CorrelationResult:

        result = CorrelationResult()

        for rule in self.rules:

            self._execute_rule(
                rule=rule,
                context=context,
                result=result,
            )

        self._remove_duplicates(result)
        self._sort_findings(result)

        return result

    def _execute_rule(
        self,
        rule: BaseCorrelationRule,
        context: InvestigationContext,
        result: CorrelationResult,
    ) -> None:

        try:

            findings = rule.evaluate(context)

            for finding in findings:

                result.add_finding(finding)

        except Exception as exc:

            self._handle_rule_exception(
                rule,
                exc,
                result,
            )

    def _handle_rule_exception(
        self,
        rule: BaseCorrelationRule,
        exception: Exception,
        result: CorrelationResult,
    ) -> None:

        result.add_finding(

            CorrelationFinding(

                title=f"Falha na regra '{rule.name}'",
                description=str(exception),
                severity="warning",
                rule_id=rule.rule_id,
                icon="error",

            )

        )

    def _remove_duplicates(
        self,
        result: CorrelationResult,
    ) -> None:

        unique = {}
        
        for finding in result.findings:

            key = (
                finding.rule_id,
                finding.title,
                tuple(sorted(finding.related_files)),
            )

            unique[key] = finding

        result.findings = list(unique.values())

    def _sort_findings(
        self,
        result: CorrelationResult,
    ) -> None:

        severity_order = {

            "critical": 0,
            "warning": 1,
            "ok": 2,
            "info": 3,

        }

        result.findings.sort(

            key=lambda finding: (

                severity_order.get(
                    finding.severity,
                    99,
                ),

                finding.title,

            )

        )
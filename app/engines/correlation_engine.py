from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class CorrelationEngine:
    """
    Executa as regras investigativas e consolida os Findings gerados.
    """

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
        *,
        rule: BaseCorrelationRule,
        context: InvestigationContext,
        result: CorrelationResult,
    ) -> None:
        try:
            findings = rule.evaluate(context)

            for finding in findings:
                result.add_finding(finding)

        except Exception as exc:
            result.add_finding(
                CorrelationFinding(
                    title=f"Falha na regra '{rule.name}'",
                    description=str(exc),
                    severity="warning",
                    rule_id=rule.rule_id,
                    icon="error",
                    metadata={
                        "regra": rule.rule_id,
                        "erro": str(exc),
                    },
                )
            )

    def _remove_duplicates(
        self,
        result: CorrelationResult,
    ) -> None:
        unique_findings: dict[
            tuple[str, str, str, str, str],
            CorrelationFinding,
        ] = {}

        for finding in result.findings:
            rule_id = str(
                getattr(
                    finding,
                    "rule_id",
                    "",
                )
            )

            title = str(
                getattr(
                    finding,
                    "title",
                    "",
                )
            )

            description = self._get_description(
                finding
            )

            source_file = self._get_source_file(
                finding
            )

            target_file = self._get_target_file(
                finding
            )

            key = (
                rule_id,
                title,
                description,
                source_file,
                target_file,
            )

            if key not in unique_findings:
                unique_findings[key] = finding

        result.findings = list(
            unique_findings.values()
        )

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
                    self._normalize_severity(
                        getattr(
                            finding,
                            "severity",
                            "info",
                        )
                    ),
                    99,
                ),
                str(
                    getattr(
                        finding,
                        "title",
                        "",
                    )
                ).lower(),
            )
        )

    def _get_description(
        self,
        finding: CorrelationFinding,
    ) -> str:
        description = getattr(
            finding,
            "description",
            None,
        )

        if description:
            return str(description)

        return str(
            getattr(
                finding,
                "message",
                "",
            )
        )

    def _get_source_file(
        self,
        finding: CorrelationFinding,
    ) -> str:
        source_file = getattr(
            finding,
            "source_file",
            None,
        )

        if source_file:
            return str(source_file)

        related_files = getattr(
            finding,
            "related_files",
            [],
        )

        if isinstance(
            related_files,
            list,
        ) and related_files:
            return str(
                related_files[0]
            )

        return ""

    def _get_target_file(
        self,
        finding: CorrelationFinding,
    ) -> str:
        target_file = getattr(
            finding,
            "target_file",
            None,
        )

        if target_file:
            return str(target_file)

        related_files = getattr(
            finding,
            "related_files",
            [],
        )

        if (
            isinstance(
                related_files,
                list,
            )
            and len(related_files) > 1
        ):
            return str(
                related_files[1]
            )

        return ""

    @staticmethod
    def _normalize_severity(
        severity: object,
    ) -> str:
        value = getattr(
            severity,
            "value",
            severity,
        )

        normalized = str(
            value
        ).strip().lower()

        aliases = {
            "success": "ok",
            "warn": "warning",
            "danger": "critical",
            "error": "critical",
        }

        return aliases.get(
            normalized,
            normalized or "info",
        )
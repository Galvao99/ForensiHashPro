from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import Badge


class CorrelationEngine:
    """
    Executa as regras de investigação e consolida os findings gerados.
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
        self._prepare_for_display(
            result=result,
            context=context,
        )
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
                rule=rule,
                exception=exc,
                result=result,
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
                metadata={
                    "regra": rule.rule_id,
                    "erro": str(exception),
                },
            )
        )

    def _remove_duplicates(
        self,
        result: CorrelationResult,
    ) -> None:
        unique: dict[
            tuple[str, str, str, str],
            CorrelationFinding,
        ] = {}

        for finding in result.findings:
            source_file = getattr(
                finding,
                "source_file",
                None,
            )

            target_file = getattr(
                finding,
                "target_file",
                None,
            )

            key = (
                str(
                    getattr(
                        finding,
                        "rule_id",
                        "",
                    )
                ),
                str(
                    getattr(
                        finding,
                        "title",
                        "",
                    )
                ),
                str(source_file or ""),
                str(target_file or ""),
            )

            if key not in unique:
                unique[key] = finding

        result.findings = list(unique.values())

    def _prepare_for_display(
        self,
        *,
        result: CorrelationResult,
        context: InvestigationContext,
    ) -> None:
        for finding in result.findings:
            source_key = finding.source_file
            target_key = finding.target_file

            finding.source_evidence_key = source_key
            finding.target_evidence_key = target_key

            finding.title = self._translate_text(
                finding.title,
                context,
            )
            finding.description = self._translate_text(
                finding.description,
                context,
            )
            finding.source_file = self._display_name(
                source_key,
                context,
            )
            finding.target_file = self._display_name(
                target_key,
                context,
            )
            finding.badges = [
                Badge(
                    text=self._translate_text(
                        badge.text,
                        context,
                    ),
                    color=badge.color,
                    icon=badge.icon,
                    tooltip=self._translate_text(
                        badge.tooltip,
                        context,
                    ),
                )
                for badge in finding.badges
            ]
            finding.metadata = self._translate_value(
                finding.metadata,
                context,
            )

    @staticmethod
    def _display_name(
        evidence_key: str | None,
        context: InvestigationContext,
    ) -> str | None:
        if evidence_key is None:
            return None

        return context.display_name_for(evidence_key)

    def _translate_text(
        self,
        value: str,
        context: InvestigationContext,
    ) -> str:
        translated = value

        display_names = sorted(
            context.display_names.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for evidence_key, display_name in display_names:
            translated = translated.replace(
                evidence_key,
                display_name,
            )

        return translated

    def _translate_value(
        self,
        value: object,
        context: InvestigationContext,
    ) -> object:
        if isinstance(value, str):
            return self._translate_text(value, context)

        if isinstance(value, dict):
            return {
                key: self._translate_value(item, context)
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                self._translate_value(item, context)
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                self._translate_value(item, context)
                for item in value
            )

        return value

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

    @staticmethod
    def _normalize_severity(
        severity: object,
    ) -> str:
        value = getattr(
            severity,
            "value",
            severity,
        )

        normalized = str(value).strip().lower()

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

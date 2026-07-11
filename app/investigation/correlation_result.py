from dataclasses import dataclass, field

from app.investigation.correlation_finding import CorrelationFinding


@dataclass(slots=True)
class CorrelationResult:
    """
    Resultado consolidado da investigação.
    """

    findings: list[CorrelationFinding] = field(
        default_factory=list
    )

    def add_finding(
        self,
        finding: CorrelationFinding,
    ) -> None:
        self.findings.append(finding)

    def _count_by_severity(
        self,
        severity: str,
    ) -> int:
        return sum(
            1
            for finding in self.findings
            if finding.severity == severity
        )

    @property
    def total_findings(self) -> int:
        return len(self.findings)

    @property
    def has_issues(self) -> bool:
        return any(
            finding.severity in {
                "warning",
                "critical",
            }
            for finding in self.findings
        )

    @property
    def is_consistent(self) -> bool:
        return not self.has_issues

    @property
    def is_empty(self) -> bool:
        return not self.findings

    @property
    def warning_count(self) -> int:
        return self._count_by_severity("warning")

    @property
    def critical_count(self) -> int:
        return self._count_by_severity("critical")

    @property
    def success_count(self) -> int:
        return self._count_by_severity("ok")

    @property
    def info_count(self) -> int:
        return self._count_by_severity("info")

    @property
    def warnings(self) -> list[CorrelationFinding]:
        return [
            finding
            for finding in self.findings
            if finding.severity == "warning"
        ]

    @property
    def critical(self) -> list[CorrelationFinding]:
        return [
            finding
            for finding in self.findings
            if finding.severity == "critical"
        ]

    @property
    def success(self) -> list[CorrelationFinding]:
        return [
            finding
            for finding in self.findings
            if finding.severity == "ok"
        ]

    @property
    def infos(self) -> list[CorrelationFinding]:
        return [
            finding
            for finding in self.findings
            if finding.severity == "info"
        ]

    @property
    def summary(self) -> dict[str, int]:
        return {
            "critical": self.critical_count,
            "warning": self.warning_count,
            "ok": self.success_count,
            "info": self.info_count,
            "total": self.total_findings,
        }
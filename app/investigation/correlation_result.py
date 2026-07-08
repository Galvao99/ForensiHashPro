from dataclasses import dataclass, field

from app.investigation.correlation_finding import CorrelationFinding


@dataclass(slots=True)
class CorrelationResult:
    findings: list[CorrelationFinding] = field(default_factory=list)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity in {"warning", "critical"} for f in self.findings)

    @property
    def is_consistent(self) -> bool:
        return not self.has_warnings

    def add_finding(self, finding: CorrelationFinding) -> None:
        self.findings.append(finding)
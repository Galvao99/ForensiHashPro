from app.models import Finding, MetadataResult
from app.rules.gps_rule import GpsRule
from app.rules.producer_rule import ProducerRule
from app.rules.suspicious_software_rule import SuspiciousSoftwareRule


class FindingsEngine:
    """Executa regras de análise e retorna achados periciais interpretados."""

    def __init__(self) -> None:
        self.rules = [
            ProducerRule(),
            SuspiciousSoftwareRule(),
            GpsRule(),
        ]

    def analyze(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

        for rule in self.rules:
            findings.extend(rule.apply(metadata))

        return findings
from app.models import Finding, MetadataResult
from app.rules.gps_rule import GpsRule
from app.rules.producer_rule import ProducerRule


class FindingsEngine:
    """Executa regras de análise e retorna achados periciais."""

    def __init__(self) -> None:
        self.rules = [
            ProducerRule(),
            GpsRule(),
        ]

    def analyze(self, metadata: MetadataResult) -> list[Finding]:
        
        findings: list[Finding] = []

        for rule in self.rules:
            findings.extend(rule.apply(metadata))

        return findings
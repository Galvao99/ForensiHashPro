from app.models import Finding, MetadataResult
from app.models.integrity_result import IntegrityResult
from app.models.biometric_report import BiometricReport
from app.rules.biometric_report_rule import BiometricReportRule
from app.rules.gps_rule import GpsRule
from app.rules.integrity_rule import IntegrityRule
from app.rules.producer_rule import ProducerRule
from app.rules.suspicious_software_rule import SuspiciousSoftwareRule


class FindingsEngine:
    """Executa regras de análise e retorna achados periciais interpretados."""

    def __init__(self) -> None:
        self.metadata_rules = [
            ProducerRule(),
            SuspiciousSoftwareRule(),
            GpsRule(),
        ]

        self.integrity_rules = [
            IntegrityRule(),
        ]

        self.biometric_rules = [
            BiometricReportRule(),
        ]

    def analyze(
        self,
        metadata: MetadataResult,
        integrity: IntegrityResult | None = None,
        biometric_report: BiometricReport | None = None,
    ) -> list[Finding]:
        findings: list[Finding] = []

        findings.extend(self._analyze_metadata(metadata))

        if integrity:
            findings.extend(self._analyze_integrity(integrity))

        if biometric_report:
            findings.extend(
                self._analyze_biometric(biometric_report)
            )

        return findings

    def _analyze_metadata(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

        for rule in self.metadata_rules:
            findings.extend(rule.apply(metadata))

        return findings

    def _analyze_integrity(self, integrity: IntegrityResult) -> list[Finding]:
        findings: list[Finding] = []

        for rule in self.integrity_rules:
            findings.extend(rule.apply(integrity))

        return findings

    def _analyze_biometric(
        self,
        report: BiometricReport,
    ) -> list[Finding]:
        findings: list[Finding] = []

        for rule in self.biometric_rules:
            findings.extend(rule.apply(report))

        return findings

from app.enum.severity import Severity
from app.models import Finding, MetadataResult
from app.rules.base_rule import MetadataRule


class GpsRule(MetadataRule):
    """Identifica presença de metadados GPS."""

    def apply(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

        has_gps = any("gps" in key.lower() for key in metadata.raw.keys())

        if has_gps:
            findings.append(
                Finding(
                    severity=Severity.INFO,
                    category="GPS",
                    title="Metadados GPS encontrados",
                    description="O arquivo contém campos de metadados relacionados a geolocalização GPS.",
                    evidence_source="Metadados GPS",
                    observed_value="Campos GPS presentes",
                    recommendation="Conferir latitude, longitude, precisão e coerência com os demais elementos do caso.",
                    score=0.90,
                )
            )

        return findings
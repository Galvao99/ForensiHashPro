from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class AnalysisCapability(str, Enum):
    BASIC_IDENTIFICATION = "basic_identification"
    HASHING = "hashing"
    METADATA = "metadata"
    STRUCTURE = "structure"
    BASIC_SIGNATURES = "basic_signatures"
    BASIC_FINDINGS = "basic_findings"
    ARCHIVE_INSPECTION = "archive_inspection"
    CONTENT_EXTRACTION = "content_extraction"
    OCR = "ocr"
    ENTITY_EXTRACTION = "entity_extraction"
    IP_ANALYSIS = "ip_analysis"
    TEMPORAL_ANALYSIS = "temporal_analysis"
    CROSS_ARTIFACT_CORRELATION = "cross_artifact_correlation"
    SPECIALIZED_PARSERS = "specialized_parsers"
    BIOMETRIC_ANALYSIS = "biometric_analysis"


class AnalysisProfileName(str, Enum):
    FREE = "free"
    PRO = "pro"


@dataclass(frozen=True, slots=True)
class AnalysisProfile:
    name: AnalysisProfileName
    capabilities: frozenset[AnalysisCapability]
    max_artifacts: int

    def allows(self, capability: AnalysisCapability) -> bool:
        return capability in self.capabilities


_BASIC = frozenset({
    AnalysisCapability.BASIC_IDENTIFICATION,
    AnalysisCapability.HASHING,
    AnalysisCapability.METADATA,
    AnalysisCapability.STRUCTURE,
    AnalysisCapability.BASIC_SIGNATURES,
    AnalysisCapability.BASIC_FINDINGS,
    AnalysisCapability.ARCHIVE_INSPECTION,
})

FORENSIHASH_FREE = AnalysisProfile(AnalysisProfileName.FREE, _BASIC, 1)
FORENSIHASH_PRO = AnalysisProfile(AnalysisProfileName.PRO, frozenset(AnalysisCapability), 50)


def analysis_profile(value: AnalysisProfile | AnalysisProfileName | str | None) -> AnalysisProfile:
    if isinstance(value, AnalysisProfile):
        return value
    if value is None:
        return FORENSIHASH_PRO
    name = value if isinstance(value, AnalysisProfileName) else AnalysisProfileName(value.lower())
    return FORENSIHASH_FREE if name is AnalysisProfileName.FREE else FORENSIHASH_PRO


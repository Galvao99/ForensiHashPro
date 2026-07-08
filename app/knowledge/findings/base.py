from dataclasses import dataclass
from enum import Enum


class FindingSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class FindingDefinition:
    code: str
    title: str
    category: str
    severity: FindingSeverity
    nature: str
    explanation: str
    forensic_impact: str
    recommendation: str
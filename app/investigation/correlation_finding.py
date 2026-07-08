from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CorrelationFinding:
    title: str
    message: str
    severity: str = "info"  # info | ok | warning | critical
    rule_id: str = ""
    related_files: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)
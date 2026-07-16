from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BinaryFinding:
    code: str
    title: str
    description: str
    offset: int | None = None
    length: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

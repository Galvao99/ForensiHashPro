from dataclasses import dataclass, field
from typing import Any

from app.models.binary_finding import BinaryFinding
from app.models.binary_region import BinaryRegion
from app.models.binary_string import BinaryString
from app.models.entropy_region import EntropyRegion


@dataclass(slots=True)
class BinaryAnalysisResult:
    file_size: int
    header_bytes: bytes
    footer_bytes: bytes
    regions: list[BinaryRegion] = field(default_factory=list)
    strings: list[BinaryString] = field(default_factory=list)
    entropy_regions: list[EntropyRegion] = field(default_factory=list)
    findings: list[BinaryFinding] = field(default_factory=list)
    parser_name: str | None = None
    parser_details: dict[str, Any] = field(default_factory=dict)
    average_entropy: float | None = None

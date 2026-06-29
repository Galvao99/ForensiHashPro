from dataclasses import dataclass, field

from app.models.comparison_section import ComparisonSection


@dataclass(frozen=True)
class ComparisonResult:
    left_file: str
    right_file: str
    sections: list[ComparisonSection] = field(default_factory=list)
    technical_summary: str = ""
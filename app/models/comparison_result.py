from dataclasses import dataclass, field

from app.models.comparison_section import ComparisonSection


@dataclass(frozen=True)
class ComparisonResult:
    """Resultado da comparação entre duas análises forenses."""

    sections: list[ComparisonSection] = field(default_factory=list)
    technical_summary: str = ""
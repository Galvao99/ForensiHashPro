from dataclasses import dataclass


@dataclass(frozen=True)
class ComparisonSection:
    """Representa uma seção da comparação forense."""

    title: str
    status: bool
    description: str
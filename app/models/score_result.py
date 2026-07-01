from dataclasses import dataclass, field


@dataclass(frozen=True)
class ScoreSection:
    name: str
    exists: bool
    score: int
    weight: int
    description: str
    details: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ScoreResult:
    score: int
    risk_level: str
    confidence_level: str
    sections: list[ScoreSection] = field(default_factory=list)
from dataclasses import dataclass, field


@dataclass(slots=True)
class Badge:

    text: str
    color: str = "gray"


@dataclass(slots=True)
class Evidence:

    title: str
    description: str
    severity: str
    icon: str
    badges: list[Badge] = field(default_factory=list)
    details: dict = field(default_factory=dict)
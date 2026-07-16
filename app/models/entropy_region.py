from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EntropyRegion:
    offset: int
    length: int
    entropy: float
    classification: str

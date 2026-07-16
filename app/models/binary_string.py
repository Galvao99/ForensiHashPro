from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BinaryString:
    offset: int
    length: int
    encoding: str
    value: str
    category: str = "generic"

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class BinaryRegion:
    """A neutral description of a byte region found in a file."""

    offset: int
    length: int | None
    kind: str
    signature: str | None
    description: str
    status: str = "candidate"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def hexadecimal_offset(self) -> str:
        return f"0x{self.offset:X}"

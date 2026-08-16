from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DiffField:
    key: str
    left: str | None
    right: str | None
    state: str


@dataclass(frozen=True, slots=True)
class DiffGroup:
    title: str
    fields: tuple[DiffField, ...] = ()


@dataclass(frozen=True, slots=True)
class ComparisonView:
    left_id: str
    right_id: str
    groups: tuple[DiffGroup, ...]
    matches: tuple[tuple[str, str, str], ...] = ()
    engine_result: object | None = None

    @property
    def match_count(self) -> int:
        return len(self.matches)

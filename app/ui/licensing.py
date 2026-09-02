from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class LicenseSummaryViewModel:
    """Display-only licensing state supplied by a future authoritative provider."""

    label: str
    detail: str | None = None


class LicenseSummaryProvider(Protocol):
    """Boundary for future Licensing/Entitlements integration.

    The Home does not render a license section while no provider is installed.
    """

    def summary(self) -> LicenseSummaryViewModel | None: ...

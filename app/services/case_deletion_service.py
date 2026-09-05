from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Protocol


class CaseCatalogWriter(Protocol):
    def remove(self, case_id: str) -> bool: ...


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeleteCaseResult:
    success: bool
    case_id: str
    removed_recent_entry: bool = False
    error: str | None = None


class CaseDeletionService:
    """Deletes ForensiHash-owned local case state, never source evidence."""

    def __init__(self, catalog: CaseCatalogWriter) -> None:
        self._catalog = catalog

    def delete_case(self, case_id: str) -> DeleteCaseResult:
        normalized = str(case_id).strip()
        if not normalized:
            return DeleteCaseResult(False, normalized, error="invalid_case_id")
        try:
            removed = self._catalog.remove(normalized)
        except (OSError, ValueError):
            LOGGER.exception("Failed to remove local case catalog entry", extra={"case_id": normalized})
            return DeleteCaseResult(False, normalized, error="catalog_update_failed")
        return DeleteCaseResult(True, normalized, removed_recent_entry=removed)

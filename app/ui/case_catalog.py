from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(slots=True)
class RecentCase:
    """Presentation metadata for a locally opened case.

    Analysis results remain owned by the existing analysis/cache layers.
    """

    name: str
    source_path: str
    file_count: int
    last_opened: str
    case_id: str = ""


class CaseCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list(self) -> list[RecentCase]:
        return self._load(require_available=True)[:12]

    def _load(self, *, require_available: bool) -> list[RecentCase]:
        if not self.path.exists():
            return []
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        if not isinstance(payload, list):
            return []
        cases: list[RecentCase] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                case = RecentCase(
                    name=str(item["name"]),
                    source_path=str(item["source_path"]),
                    file_count=max(0, int(item.get("file_count", 0))),
                    last_opened=str(item["last_opened"]),
                    case_id=str(item.get("case_id") or item["source_path"]),
                )
            except (KeyError, TypeError, ValueError):
                continue
            try:
                source_is_available = Path(case.source_path).exists()
            except OSError:
                source_is_available = False
            if case.name.strip() and (source_is_available or not require_available):
                cases.append(case)
        return cases

    def touch(self, name: str, source_path: Path, file_count: int) -> RecentCase:
        resolved = str(source_path.resolve())
        recent = RecentCase(
            name=name.strip(),
            source_path=resolved,
            file_count=max(0, file_count),
            last_opened=datetime.now(timezone.utc).isoformat(),
            case_id=resolved,
        )
        cases = [item for item in self.list() if item.case_id != recent.case_id]
        cases.insert(0, recent)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(item) for item in cases[:12]], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return recent

    def remove(self, case_id: str) -> bool:
        """Atomically remove only the catalog entry identified by ``case_id``."""
        normalized = str(case_id).strip()
        if not normalized:
            raise ValueError("case_id must not be empty")
        cases = self._load(require_available=False)
        remaining = [item for item in cases if item.case_id != normalized]
        if len(remaining) == len(cases):
            return False
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(item) for item in remaining], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return True

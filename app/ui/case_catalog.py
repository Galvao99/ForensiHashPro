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


class CaseCatalog:
    def __init__(self, path: Path) -> None:
        self.path = path

    def list(self) -> list[RecentCase]:
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
                )
            except (KeyError, TypeError, ValueError):
                continue
            try:
                source_is_available = Path(case.source_path).exists()
            except OSError:
                source_is_available = False
            if case.name.strip() and source_is_available:
                cases.append(case)
        return cases[:12]

    def touch(self, name: str, source_path: Path, file_count: int) -> RecentCase:
        resolved = str(source_path.resolve())
        recent = RecentCase(
            name=name.strip(),
            source_path=resolved,
            file_count=max(0, file_count),
            last_opened=datetime.now(timezone.utc).isoformat(),
        )
        cases = [item for item in self.list() if item.source_path != resolved]
        cases.insert(0, recent)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps([asdict(item) for item in cases[:12]], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(self.path)
        return recent

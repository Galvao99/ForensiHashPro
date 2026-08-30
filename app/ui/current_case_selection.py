from dataclasses import dataclass
from pathlib import Path

from app.models import AnalysisResult


@dataclass(slots=True)
class CurrentCaseSelection:
    """Canonical identity and state of the file selected in the Desktop case."""

    case_id: str
    file_path: Path
    status: str = "pending"
    result: AnalysisResult | None = None
    error: str | None = None

    @property
    def key(self) -> str:
        return str(self.file_path.resolve())

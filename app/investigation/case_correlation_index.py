from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from app.investigation.investigation_context import InvestigationContext
from app.investigation.investigation_context_builder import InvestigationContextBuilder
from app.models import AnalysisResult


@dataclass(slots=True)
class CaseCorrelationIndex:
    """Índice leve e isolado de resultados já produzidos para um Caso."""

    case_id: str
    context_builder: InvestigationContextBuilder
    _results: dict[str, AnalysisResult] = field(default_factory=dict)
    _context: InvestigationContext | None = None

    @staticmethod
    def evidence_key(result: AnalysisResult) -> str:
        return str(Path(result.file_info.path).resolve())

    @property
    def results(self) -> tuple[AnalysisResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))

    def replace(self, results: Iterable[AnalysisResult]) -> InvestigationContext:
        replacement = {
            self.evidence_key(result): result
            for result in results
        }
        if replacement != self._results:
            self._results = replacement
            self._context = None
        return self.context

    def add(self, result: AnalysisResult) -> InvestigationContext:
        key = self.evidence_key(result)
        if self._results.get(key) is not result:
            self._results[key] = result
            self._context = None
        return self.context

    def remove(self, file_path: Path | str) -> InvestigationContext:
        key = str(Path(file_path).resolve())
        if self._results.pop(key, None) is not None:
            self._context = None
        return self.context

    @property
    def context(self) -> InvestigationContext:
        if self._context is None:
            self._context = self.context_builder.build(self.results)
        return self._context

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.contracts import (
    AnalysisContract,
    AnalysisState,
    LegacyAnalysisAdapter,
    ProgressEvent,
    ProgressStatus,
)
from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService


ProgressCallback = Callable[[ProgressEvent], None]


@dataclass(slots=True)
class CancellationToken:
    cancelled: bool = False

    def cancel(self) -> None:
        self.cancelled = True


@dataclass(frozen=True, slots=True)
class AnalysisExecution:
    legacy_result: AnalysisResult
    contract: AnalysisContract


class AnalysisCoordinator:
    """Caso de uso sem Qt para executar análise e montar o contrato v1."""

    def __init__(
        self,
        service: AnalysisService,
        *,
        adapter: LegacyAnalysisAdapter | None = None,
        progress: ProgressCallback | None = None,
    ) -> None:
        self.service = service
        self.adapter = adapter or LegacyAnalysisAdapter()
        self.progress = progress

    def analyze(
        self,
        evidence_path: Path,
        *,
        cancellation: CancellationToken | None = None,
    ) -> AnalysisContract:
        return self.execute(evidence_path, cancellation=cancellation).contract

    def execute(
        self,
        evidence_path: Path,
        *,
        cancellation: CancellationToken | None = None,
    ) -> AnalysisExecution:
        analysis_id = str(uuid4())
        token = cancellation or CancellationToken()
        self._emit(analysis_id, "analysis", ProgressStatus.STARTED, "Análise iniciada.", 0)
        if token.cancelled:
            self._emit(
                analysis_id, "analysis", ProgressStatus.CANCELLED, "Análise cancelada.", None
            )
            raise AnalysisCancelledError("Análise cancelada antes da aquisição.")

        self._emit(
            analysis_id,
            "evidence_acquisition",
            ProgressStatus.RUNNING,
            "Adquirindo cópia controlada da evidência.",
            5,
        )
        try:
            legacy = self.service.analyze(Path(evidence_path), analysis_id=analysis_id)
            if token.cancelled:
                self._emit(
                    analysis_id, "analysis", ProgressStatus.CANCELLED, "Análise cancelada.", None
                )
                raise AnalysisCancelledError("Análise cancelada após o processamento atual.")
            contract = self.adapter.convert(legacy)
        except AnalysisCancelledError:
            raise
        except Exception:
            self._emit(
                analysis_id, "analysis", ProgressStatus.FAILED, "A análise falhou.", None
            )
            raise

        self._emit(
            analysis_id, "analysis", ProgressStatus.COMPLETED, "Análise concluída.", 100
        )
        return AnalysisExecution(legacy, contract)

    def _emit(
        self,
        analysis_id: str,
        step: str,
        status: ProgressStatus,
        message: str,
        percentage: int | None,
    ) -> None:
        if self.progress is None:
            return
        event_id = str(
            uuid5(
                NAMESPACE_URL,
                f"forensihash:{analysis_id}:progress:{step}:{status.value}:{percentage}",
            )
        )
        self.progress(
            ProgressEvent(
                event_id,
                analysis_id,
                step,
                status,
                message,
                datetime.now(timezone.utc),
                percentage,
            )
        )


class AnalysisCancelledError(RuntimeError):
    state = AnalysisState.CANCELLED

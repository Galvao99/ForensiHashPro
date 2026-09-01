from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService
from app.application import AnalysisCoordinator, CancellationToken
from app.contracts import ProgressEvent
from app.observability import ExecutionMetric, ExecutionStatus, ObservabilityService
from datetime import datetime, timezone
from time import perf_counter


class AnalysisWorker(QObject):
    """
    Executa a análise de arquivos fora da thread principal da interface.
    """

    progress_changed = Signal(int, str)
    file_analyzed = Signal(object)
    contract_analyzed = Signal(object)
    file_failed = Signal(str, str)
    file_state_changed = Signal(str, str)
    case_progress_changed = Signal(object)

    investigation_completed = Signal(object)
    completed = Signal(list)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        analysis_service: AnalysisService,
        files: Sequence[Path],
        case_id: str | None = None,
        cached_results: dict[str, AnalysisResult] | None = None,
        observability: ObservabilityService | None = None,
    ) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.files = [
            Path(file_path)
            for file_path in files
        ]
        self.case_id = case_id
        self.cached_results = dict(cached_results or {})
        self.observability = observability
        self.case_ref: str | None = None

        self._cancelled = False
        self._cancellation = CancellationToken()
        self._core_base = 0.0
        self._core_span = 88.0

    def _on_core_progress(self, event: ProgressEvent) -> None:
        if event.percentage is not None:
            percentage = int(
                self._core_base + (event.percentage / 100) * self._core_span
            )
            self.progress_changed.emit(percentage, event.message)

    @Slot()
    def run(self) -> None:
        try:
            if not self.files:
                self.completed.emit([])
                return

            results: list[AnalysisResult] = []
            total_files = len(self.files)
            failed_files = 0
            partial_files = 0
            cache_hits = 0
            cache_misses = 0
            if self.case_id:
                self.investigation_completed.emit(
                    self.analysis_service.correlate_case(self.case_id, results)
                )

            for index, file_path in enumerate(
                self.files,
                start=1,
            ):
                if self._cancelled:
                    break

                resolved_path = str(file_path.resolve())
                cached = self.cached_results.get(resolved_path)
                if cached is not None:
                    cache_hits += 1
                    results.append(cached)
                    self.file_state_changed.emit(resolved_path, "analyzed")
                    self.file_analyzed.emit(cached)
                    self._emit_case_progress(total_files, len(results), failed_files, "")
                    self._update_observability(len(results), partial_files, failed_files,
                                               total_files, cache_hits, cache_misses,
                                               first_result=True)
                    if self.case_id:
                        self.investigation_completed.emit(
                            self.analysis_service.correlate_case(self.case_id, results)
                        )
                    continue

                start_percentage = int(
                    ((index - 1) / total_files) * 88
                )

                self.progress_changed.emit(
                    start_percentage,
                    (
                        f"Analisando {index} de {total_files}: "
                        f"{file_path.name}"
                    ),
                )
                self.file_state_changed.emit(resolved_path, "analyzing")
                self._emit_case_progress(
                    total_files, len(results), failed_files, file_path.name
                )

                try:
                    cache_misses += 1
                    metric_started = datetime.now(timezone.utc)
                    metric_started_counter = perf_counter()
                    job_id = self.observability.start_job(
                        case_ref=self.case_ref, file_path=str(file_path),
                        engine_id="analysis_pipeline", operation="analyze_file",
                    ) if self.observability else None
                    self._core_base = ((index - 1) / total_files) * 88
                    self._core_span = 88 / total_files
                    execution = AnalysisCoordinator(
                        self.analysis_service,
                        progress=self._on_core_progress,
                    ).execute(
                        file_path,
                        cancellation=self._cancellation,
                    )
                    result = execution.legacy_result

                except Exception as error:
                    failed_files += 1
                    self.file_state_changed.emit(resolved_path, "failed")
                    self.file_failed.emit(
                        str(file_path),
                        str(error),
                    )
                    self._emit_case_progress(
                        total_files, len(results), failed_files, ""
                    )
                    if self.observability:
                        finished = datetime.now(timezone.utc)
                        self.observability.record_metric(ExecutionMetric(
                            str(job_id), "analysis_pipeline", metric_started, finished,
                            duration_ms=(perf_counter() - metric_started_counter) * 1000,
                            status=ExecutionStatus.FAILED, case_ref=self.case_ref,
                            file_ref=None, operation="analyze_file",
                            error_code="analysis_failed", cache_hit=False,
                        ))
                        self.observability.record_error(component_id="analysis_pipeline",
                            operation="analyze_file", error_code="analysis_failed", error=error,
                            file_path=str(file_path), case_ref=self.case_ref)
                        if job_id: self.observability.finish_job(job_id)
                    self._update_observability(len(results), partial_files, failed_files,
                                               total_files, cache_hits, cache_misses)
                    continue

                results.append(result)
                is_partial = any(getattr(step.status, "value", step.status) in {"partial", "failed", "unavailable", "limit_exceeded"} for step in result.processing_steps)
                partial_files += int(is_partial)
                if self.observability:
                    finished = datetime.now(timezone.utc)
                    self.observability.record_metric(ExecutionMetric(
                        str(job_id), "analysis_pipeline", metric_started, finished,
                        duration_ms=(perf_counter() - metric_started_counter) * 1000,
                        status=ExecutionStatus.PARTIAL if is_partial else ExecutionStatus.COMPLETED,
                        case_ref=self.case_ref, operation="analyze_file", cache_hit=False,
                    ))
                    if job_id: self.observability.finish_job(job_id)
                    self._record_step_metrics(result)
                self.file_analyzed.emit(result)
                self.contract_analyzed.emit(execution.contract)
                self.file_state_changed.emit(resolved_path, "analyzed")
                if self.case_id:
                    self.investigation_completed.emit(
                        self.analysis_service.correlate_case(self.case_id, results)
                    )
                self._emit_case_progress(
                    total_files, len(results), failed_files, ""
                )
                self._update_observability(len(results), partial_files, failed_files,
                                           total_files, cache_hits, cache_misses,
                                           first_result=True)

                end_percentage = int(
                    (index / total_files) * 88
                )

                self.progress_changed.emit(
                    end_percentage,
                    f"Análise concluída: {file_path.name}",
                )

            if self._cancelled:
                self.completed.emit(results)
                return

            correlation_result = None

            if results and not self.case_id:
                self.progress_changed.emit(
                    92,
                    "Correlacionando vestígios entre os arquivos...",
                )

                correlation_result = self.analysis_service.correlate(results)

                self.investigation_completed.emit(
                    correlation_result
                )

            self.progress_changed.emit(
                100,
                "Análise concluída.",
            )

            self.completed.emit(results)
            self._update_observability(len(results), partial_files, failed_files,
                                       total_files, cache_hits, cache_misses, finished=True)

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()

    def _record_step_metrics(self, result: AnalysisResult) -> None:
        if self.observability is None:
            return
        for step in result.processing_steps:
            raw = getattr(step.status, "value", step.status)
            if raw == "skipped":
                continue
            status = (ExecutionStatus.FAILED if raw in {"failed", "unavailable"}
                      else ExecutionStatus.PARTIAL if raw in {"partial", "limit_exceeded"}
                      else ExecutionStatus.COMPLETED)
            self.observability.record_metric(ExecutionMetric(
                execution_id=f"{result.analysis_id}:{step.code}", engine_id=step.component,
                started_at=step.started_at_utc, finished_at=step.finished_at_utc,
                status=status, case_ref=self.case_ref, operation=step.code,
                error_code=step.issues[0].code if step.issues else None,
            ))

    def _update_observability(self, analyzed: int, partial: int, failed: int,
                              total: int, hits: int, misses: int, *,
                              first_result: bool = False, finished: bool = False) -> None:
        if self.observability:
            self.observability.update_case(
                completed=max(0, analyzed - partial), partial=partial, failed=failed,
                pending=max(0, total - analyzed - failed), running=0,
                cache_hits=hits, cache_misses=misses,
                first_result=first_result, finished=finished,
            )

    def cancel(self) -> None:
        self._cancelled = True
        self._cancellation.cancel()

    def _emit_case_progress(
        self,
        total: int,
        analyzed: int,
        failed: int,
        current_file: str,
    ) -> None:
        self.case_progress_changed.emit({
            "total": total,
            "analyzed": analyzed,
            "failed": failed,
            "pending": max(0, total - analyzed - failed),
            "current_file": current_file,
        })

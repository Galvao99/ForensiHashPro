from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService
from app.application import AnalysisCoordinator, CancellationToken
from app.application.analysis_coordinator import AnalysisCancelledError
from app.contracts import ProgressEvent
from app.observability import ExecutionMetric, ExecutionStatus, ObservabilityService
from app.observability.models import CorrelationRuleMetric
from app.observability.sanitization import safe_ref
from app.observability.profiling import ProfilingBinding, profile_call, profiling_scope
from datetime import datetime, timezone
from time import perf_counter
from copy import deepcopy

from app.evidence import EvidenceContentIdentity


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
    canonical_case_completed = Signal(object)
    canonical_case_failed = Signal(str, str)
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
        self._canonical_failed = False
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
        results: list[AnalysisResult] = []
        total_files = len(self.files)
        failed_files = 0
        partial_files = 0
        cache_hits = 0
        cache_misses = 0
        try:
            if not self.files:
                self._update_observability(0, 0, 0, 0, 0, 0, finished=True)
                self.completed.emit([])
                return

            for index, file_path in enumerate(
                self.files,
                start=1,
            ):
                if self._cancelled:
                    break

                resolved_path = str(file_path.resolve())
                job_id = self._start_observability_job(file_path)
                lookup_started = perf_counter()
                cached = self._validated_cached_result(
                    file_path, self.cached_results.get(resolved_path)
                )
                lookup_ms = (perf_counter() - lookup_started) * 1000
                if cached is not None:
                    cache_hits += 1
                    results.append(cached)
                    cached_is_partial = self._is_partial_result(cached)
                    self._record_cache_metric(
                        file_path,
                        hit=True,
                        duration_ms=lookup_ms,
                        size_bytes=cached.file_info.size_bytes,
                        status=(
                            ExecutionStatus.PARTIAL
                            if cached_is_partial
                            else ExecutionStatus.COMPLETED
                        ),
                    )
                    partial_files += int(cached_is_partial)
                    self.file_state_changed.emit(resolved_path, "analyzed")
                    self._update_observability(len(results), partial_files, failed_files,
                                               total_files, cache_hits, cache_misses,
                                               first_result=self._is_useful_result(cached))
                    self.file_analyzed.emit(cached)
                    self._finish_observability_job(
                        job_id,
                        ExecutionStatus.PARTIAL
                        if cached_is_partial
                        else ExecutionStatus.COMPLETED,
                    )
                    self._emit_case_progress(total_files, len(results), failed_files, "")
                    self._update_observability(len(results), partial_files, failed_files,
                                               total_files, cache_hits, cache_misses,
                                               first_result=self._is_useful_result(cached))
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

                cache_misses += 1
                self._record_cache_metric(file_path, hit=False, duration_ms=lookup_ms)
                metric_started = datetime.now(timezone.utc)
                metric_started_counter = perf_counter()
                try:
                    self._core_base = ((index - 1) / total_files) * 88
                    self._core_span = 88 / total_files
                    binding = (ProfilingBinding(self.observability, self.case_ref,
                               safe_ref("file", resolved_path), self._file_size(file_path))
                               if self.observability is not None else None)
                    with profiling_scope(binding):
                        execution = AnalysisCoordinator(
                            self.analysis_service,
                            progress=self._on_core_progress,
                        ).execute(file_path, cancellation=self._cancellation)
                    result = execution.legacy_result

                except AnalysisCancelledError:
                    self._cancelled = True
                    self._record_observability_metric(ExecutionMetric(
                        str(job_id), "analysis_pipeline", metric_started, datetime.now(timezone.utc),
                        duration_ms=(perf_counter() - metric_started_counter) * 1000,
                        status=ExecutionStatus.CANCELLED, case_ref=self.case_ref,
                        file_ref=safe_ref("file", resolved_path), operation="analyze_file",
                        metadata={"size_bytes": self._file_size(file_path)},
                    ))
                    self._finish_observability_job(job_id, ExecutionStatus.CANCELLED)
                    break

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
                    if self.observability and job_id is not None:
                        finished = datetime.now(timezone.utc)
                        self._record_observability_metric(ExecutionMetric(
                            str(job_id), "analysis_pipeline", metric_started, finished,
                            duration_ms=(perf_counter() - metric_started_counter) * 1000,
                            status=ExecutionStatus.FAILED, case_ref=self.case_ref,
                            file_ref=safe_ref("file", resolved_path), operation="analyze_file",
                            error_code="analysis_failed", cache_hit=False,
                        ))
                    self._record_observability_error(error, file_path)
                    self._finish_observability_job(job_id, ExecutionStatus.FAILED)
                    self._update_observability(len(results), partial_files, failed_files,
                                               total_files, cache_hits, cache_misses)
                    continue

                results.append(result)
                is_partial = self._is_partial_result(result)
                partial_files += int(is_partial)
                if self.observability and job_id is not None:
                    finished = datetime.now(timezone.utc)
                    self._record_observability_metric(ExecutionMetric(
                        str(job_id), "analysis_pipeline", metric_started, finished,
                        duration_ms=(perf_counter() - metric_started_counter) * 1000,
                        status=ExecutionStatus.PARTIAL if is_partial else ExecutionStatus.COMPLETED,
                        case_ref=self.case_ref, file_ref=safe_ref("file", resolved_path),
                        operation="analyze_file", cache_hit=False,
                        metadata={"size_bytes": result.file_info.size_bytes},
                    ))
                self._finish_observability_job(job_id, ExecutionStatus.PARTIAL if is_partial else ExecutionStatus.COMPLETED)
                # Availability boundary immediately before publishing to the UI.
                # Signal-delivery/render latency is outside this measurement.
                self._update_observability(len(results), partial_files, failed_files,
                                           total_files, cache_hits, cache_misses,
                                           first_result=self._is_useful_result(result))
                self.file_analyzed.emit(result)
                self.contract_analyzed.emit(execution.contract)
                self.file_state_changed.emit(resolved_path, "analyzed")
                self._emit_case_progress(
                    total_files, len(results), failed_files, ""
                )
                self._update_observability(len(results), partial_files, failed_files,
                                           total_files, cache_hits, cache_misses,
                                           first_result=self._is_useful_result(result))

                end_percentage = int(
                    (index / total_files) * 88
                )

                self.progress_changed.emit(
                    end_percentage,
                    f"Análise concluída: {file_path.name}",
                )

            if self._cancelled:
                self._update_observability(len(results), partial_files, failed_files,
                                           total_files, cache_hits, cache_misses,
                                           finished=True, cancelled=True)
                self.completed.emit(results)
                return

            correlation_result = None

            if self.case_id:
                self.progress_changed.emit(
                    92,
                    "Correlacionando vestígios entre os arquivos...",
                )
                self._emit_case_correlations(results)
                if results:
                    self._emit_canonical_correlations(self.case_id, results)
            elif results:
                self.progress_changed.emit(
                    92,
                    "Correlacionando vestígios entre os arquivos...",
                )

                with self._case_profiling_scope():
                    correlation_result = profile_call("legacy_correlation", "case_correlation", self.analysis_service.correlate, results)

                self.investigation_completed.emit(
                    correlation_result
                )
                self._emit_canonical_correlations(str(self.files[0].resolve()), results)

            self.progress_changed.emit(
                100,
                "Análise concluída.",
            )

            self.completed.emit(results)
            self._update_observability(len(results), partial_files, failed_files,
                                       total_files, cache_hits, cache_misses, finished=True)

        except Exception as error:
            self._update_observability(len(results), partial_files, failed_files + 1,
                                       total_files, cache_hits, cache_misses,
                                       finished=True, session_failed=True)
            self.failed.emit(str(error))

        finally:
            self.finished.emit()

    def _emit_case_correlations(self, results: list[AnalysisResult]) -> None:
        if self.case_id is None:
            return
        with self._case_profiling_scope():
            result = profile_call("legacy_correlation", "case_correlation", self.analysis_service.correlate_case, self.case_id, results)
        self.investigation_completed.emit(result)

    def _emit_canonical_correlations(
        self, case_id: str, results: list[AnalysisResult],
    ) -> None:
        analyze = getattr(self.analysis_service, "correlate_case_canonical", None)
        if callable(analyze):
            try:
                self._mark_correlation_started()
                result = analyze(case_id, results)
                self._record_correlation_profile(result)
                self.canonical_case_completed.emit(result)
            except Exception as error:
                self._canonical_failed = True
                self.canonical_case_failed.emit(
                    case_id,
                    f"Correlação canônica indisponível ({type(error).__name__}).",
                )

    @staticmethod
    def _file_size(file_path: Path) -> int | None:
        try:
            return file_path.stat().st_size
        except OSError:
            return None

    @staticmethod
    def _validated_cached_result(
        file_path: Path, cached: AnalysisResult | None,
    ) -> AnalysisResult | None:
        if cached is None:
            return None
        try:
            cached_path = Path(cached.file_info.path).resolve()
            source_path = cached.evidence_source.original_path.resolve()
            current_path = file_path.resolve()
        except (AttributeError, OSError):
            return None
        if cached_path != current_path or source_path != current_path:
            return None
        cached_identity = EvidenceContentIdentity.from_cached_result(cached)
        if cached_identity is None:
            return None
        current_identity = EvidenceContentIdentity.calculate(file_path)
        if not cached_identity.matches(current_identity):
            return None
        return deepcopy(cached)

    def _case_profiling_scope(self):
        return profiling_scope(ProfilingBinding(self.observability, self.case_ref, None)
                               if self.observability is not None else None)

    def _record_cache_metric(
        self,
        file_path: Path,
        *,
        hit: bool,
        duration_ms: float,
        size_bytes: int | None = None,
        status: ExecutionStatus = ExecutionStatus.COMPLETED,
    ) -> None:
        if self.observability is None:
            return
        now = datetime.now(timezone.utc)
        self._record_observability_metric(ExecutionMetric(
            execution_id=f"cache:{safe_ref('file', file_path.resolve())}:{now.timestamp()}",
            engine_id="analysis_cache", started_at=now, finished_at=now,
            duration_ms=duration_ms, status=status,
            case_ref=self.case_ref, file_ref=safe_ref("file", file_path.resolve()),
            operation="lookup", cache_hit=hit,
            metadata={"size_bytes": size_bytes},
        ))

    def _record_correlation_profile(self, result: object) -> None:
        if self.observability is None:
            return
        profile = getattr(result, "performance", None)
        graph = getattr(result, "graph", None)
        if profile is None or graph is None:
            return
        try:
            rules = tuple(CorrelationRuleMetric(item.rule_id, item.duration_ms, item.findings, item.failed)
                          for item in profile.rules)
            self.observability.record_correlation(
                facts=len(graph.entities),
                occurrences=sum(item.occurrence_count for item in graph.entities),
                relations=len(graph.relations), duration_ms=profile.duration_ms,
                index_ms=profile.index_build_duration_ms,
                rules_ms=profile.rule_evaluation_duration_ms, rules=rules,
            )
        except Exception as error:
            self._report_observability_failure("record_correlation", error)

    def _mark_correlation_started(self) -> None:
        if self.observability is None:
            return
        try:
            self.observability.mark_correlation_started()
        except Exception as error:
            self._report_observability_failure("mark_correlation_started", error)

    @staticmethod
    def _is_partial_result(result: AnalysisResult) -> bool:
        partial_statuses = {"partial", "failed", "unavailable", "limit_exceeded"}
        return any(
            getattr(step.status, "value", step.status) in partial_statuses
            for step in result.processing_steps
        )

    @staticmethod
    def _is_useful_result(result: AnalysisResult) -> bool:
        """TTFR milestone: first presentable result with real successful technical work."""
        import re
        digest = getattr(result.hashes, "sha256", "")
        # A valid technical digest or nonempty parser/metadata payload qualifies.
        # Status-only StepResults (including NO_FINDINGS) never qualify.
        def has_payload(value: object) -> bool:
            if value is None:
                return False
            if isinstance(value, (str, bytes, list, tuple, dict, set, frozenset)):
                return bool(value)
            # Typed result objects (dataclasses and domain models) are technical
            # payloads. The value itself is never retained by observability.
            return True

        return bool(re.fullmatch(r"[0-9a-fA-F]{64}", digest or "")) or bool(result.metadata.raw) or any(
            getattr(step.status, "value", step.status) in {"success", "partial", "limit_exceeded"}
            and has_payload(step.value)
            for step in result.processing_steps)

    def _start_observability_job(self, file_path: Path) -> str | None:
        if self.observability is None:
            return None
        try:
            return self.observability.start_job(
                case_ref=self.case_ref,
                file_path=str(file_path),
                engine_id="analysis_pipeline",
                operation="analyze_file",
            )
        except Exception as error:
            self._report_observability_failure("start_job", error)
            return None

    def _finish_observability_job(self, job_id: str | None,
                                  outcome: ExecutionStatus = ExecutionStatus.COMPLETED) -> None:
        if self.observability is None or job_id is None:
            return
        try:
            self.observability.finish_job(job_id, outcome)
        except Exception as error:
            self._report_observability_failure("finish_job", error)

    def _record_observability_metric(self, metric: ExecutionMetric) -> None:
        if self.observability is None:
            return
        try:
            self.observability.record_metric(metric)
        except Exception as error:
            self._report_observability_failure("record_metric", error)

    def _record_observability_error(self, error: Exception, file_path: Path) -> None:
        if self.observability is None:
            return
        try:
            self.observability.record_error(
                component_id="analysis_pipeline",
                operation="analyze_file",
                error_code="analysis_failed",
                error=error,
                file_path=str(file_path),
                case_ref=self.case_ref,
            )
        except Exception as observability_error:
            self._report_observability_failure("record_error", observability_error)

    @staticmethod
    def _report_observability_failure(operation: str, error: Exception) -> None:
        print(
            f"Observabilidade indisponível em {operation} "
            f"({type(error).__name__})."
        )

    def _update_observability(self, analyzed: int, partial: int, failed: int,
                               total: int, hits: int, misses: int, *,
                               first_result: bool = False, finished: bool = False,
                               cancelled: bool = False, session_failed: bool = False) -> None:
        if self.observability:
            try:
                self.observability.update_case(
                    completed=max(0, analyzed - partial), partial=partial, failed=failed,
                    pending=max(0, total - analyzed - failed), running=0,
                    cache_hits=hits, cache_misses=misses,
                    first_result=first_result, finished=finished, cancelled=cancelled,
                    session_failed=session_failed,
                    session_degraded=self._canonical_failed,
                )
            except Exception as error:
                self._report_observability_failure("update_case", error)

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

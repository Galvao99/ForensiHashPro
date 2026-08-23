from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService
from app.application import AnalysisCoordinator, CancellationToken
from app.contracts import ProgressEvent


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
    ) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.files = [
            Path(file_path)
            for file_path in files
        ]
        self.case_id = case_id
        self.cached_results = dict(cached_results or {})

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
                    results.append(cached)
                    self.file_state_changed.emit(resolved_path, "analyzed")
                    self.file_analyzed.emit(cached)
                    self._emit_case_progress(total_files, len(results), failed_files, "")
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
                    continue

                results.append(result)
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

        except Exception as error:
            self.failed.emit(str(error))

        finally:
            self.finished.emit()

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

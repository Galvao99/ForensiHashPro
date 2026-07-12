from pathlib import Path
from typing import Sequence

from PySide6.QtCore import QObject, Signal, Slot

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService


class AnalysisWorker(QObject):
    """
    Executa a análise de arquivos fora da thread principal da interface.
    """

    progress_changed = Signal(int, str)
    file_analyzed = Signal(object)
    file_failed = Signal(str, str)

    investigation_completed = Signal(object)
    completed = Signal(list)
    failed = Signal(str)
    finished = Signal()

    def __init__(
        self,
        *,
        analysis_service: AnalysisService,
        files: Sequence[Path],
    ) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.files = [
            Path(file_path)
            for file_path in files
        ]

        self._cancelled = False

    @Slot()
    def run(self) -> None:
        try:
            if not self.files:
                self.completed.emit([])
                return

            results: list[AnalysisResult] = []
            total_files = len(self.files)

            for index, file_path in enumerate(
                self.files,
                start=1,
            ):
                if self._cancelled:
                    break

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

                try:
                    result = self.analysis_service.analyze(
                        file_path
                    )

                except Exception as error:
                    self.file_failed.emit(
                        str(file_path),
                        str(error),
                    )
                    continue

                results.append(result)
                self.file_analyzed.emit(result)

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

            if results:
                self.progress_changed.emit(
                    92,
                    "Correlacionando vestígios entre os arquivos...",
                )

                correlation_result = (
                    self.analysis_service.correlate(
                        results
                    )
                )

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
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import MetadataResult
from app.settings.tooling import ToolDetector, ToolStatus, ToolUnavailableError
from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)


class MetadataEngine:
    """Responsável por extrair metadados usando o ExifTool."""

    def __init__(
        self,
        exiftool_path: Path | None = None,
        *,
        tool_status: ToolStatus | None = None,
        timeout_seconds: int = 60,
        max_output_bytes: int = 10 * 1024 * 1024,
    ) -> None:
        if exiftool_path is not None:
            self.exiftool_status = ToolDetector._configured_status(
                "ExifTool", Path(exiftool_path).resolve(), Path(exiftool_path).resolve()
            )
        else:
            self.exiftool_status = tool_status or ToolDetector().exiftool()

        self.exiftool_path = self.exiftool_status.path
        self.timeout_seconds = timeout_seconds
        self.max_output_bytes = max_output_bytes

    def extract(self, file_path: Path) -> MetadataResult:
        step = self.extract_step(file_path)
        if step.value is not None:
            return step.value
        issue = step.issues[0]
        if isinstance(issue.original_exception, BaseException):
            raise issue.original_exception
        raise RuntimeError(issue.user_message)

    def extract_step(self, file_path: Path) -> StepResult[MetadataResult]:
        started = datetime.now(timezone.utc)
        if not self.exiftool_status.available or self.exiftool_path is None:
            error = ToolUnavailableError(self.exiftool_status)
            return self._failure_step(
                started,
                "metadata_unavailable",
                ProcessingStatus.UNAVAILABLE,
                self.exiftool_status.message,
                "A extração de metadados não foi executada porque o ExifTool está indisponível.",
                error,
            )

        command = [
            str(self.exiftool_path),
            "-json",
            "-G",
            "-a",
            "-u",
            str(file_path),
        ]

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            return self._failure_step(
                started,
                "metadata_timeout",
                ProcessingStatus.FAILED,
                "ExifTool excedeu o tempo máximo configurado.",
                "A extração de metadados excedeu o tempo máximo e foi interrompida.",
                error,
            )

        output_size = len(result.stdout.encode("utf-8", errors="replace"))
        error_size = len(result.stderr.encode("utf-8", errors="replace"))
        if output_size + error_size > self.max_output_bytes:
            return self._failure_step(
                started,
                "metadata_output_limit",
                ProcessingStatus.LIMIT_EXCEEDED,
                "A saída do ExifTool excedeu o limite configurado.",
                "A saída de metadados excedeu o limite de segurança.",
                None,
            )

        if result.returncode != 0:
            error = RuntimeError("ExifTool retornou código diferente de zero.")
            return self._failure_step(
                started,
                "metadata_process_failed",
                ProcessingStatus.FAILED,
                f"ExifTool terminou com código {result.returncode}.",
                "O ExifTool não conseguiu concluir a extração de metadados.",
                error,
                {"return_code": result.returncode},
            )

        try:
            data: list[dict[str, Any]] = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as error:
            return self._failure_step(
                started,
                "metadata_invalid_output",
                ProcessingStatus.FAILED,
                "ExifTool retornou JSON inválido.",
                "A ferramenta de metadados retornou uma resposta inválida.",
                error,
            )

        if not data:
            return StepResult(
                code="metadata_extraction",
                component="metadata",
                status=ProcessingStatus.NO_FINDINGS,
                technical_message="ExifTool concluiu sem metadados.",
                user_message="A extração foi concluída e nenhum metadado foi retornado.",
                value=MetadataResult(raw={}),
                started_at_utc=started,
                finished_at_utc=datetime.now(timezone.utc),
            )

        return StepResult(
            code="metadata_extraction",
            component="metadata",
            status=ProcessingStatus.SUCCESS,
            technical_message="ExifTool concluiu a extração.",
            user_message="Metadados extraídos com sucesso.",
            value=MetadataResult(raw=data[0]),
            started_at_utc=started,
            finished_at_utc=datetime.now(timezone.utc),
        )

    @staticmethod
    def _failure_step(
        started: datetime,
        code: str,
        status: ProcessingStatus,
        technical: str,
        user: str,
        error: BaseException | None,
        details: dict[str, Any] | None = None,
    ) -> StepResult[MetadataResult]:
        issue = ProcessingIssue(
            code=code,
            status=status,
            technical_message=technical,
            user_message=user,
            component="metadata",
            details=details or {},
            impact=ProcessingImpact.ANALYSIS_PARTIAL,
            original_exception=error,
        )
        return StepResult(
            code="metadata_extraction",
            component="metadata",
            status=status,
            technical_message=technical,
            user_message=user,
            issues=[issue],
            started_at_utc=started,
            finished_at_utc=datetime.now(timezone.utc),
        )

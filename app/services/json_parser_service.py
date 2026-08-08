import json
from pathlib import Path
from typing import Any

from app.models.json_analysis_result import (
    JsonAnalysisResult,
    JsonField,
)
from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)


class JsonParserService:
    """
    Adaptador Python para o parser JSON desenvolvido em Rust.
    """

    SUPPORTED_EXTENSIONS = {
        ".json",
        ".jsonl",
        ".ndjson",
    }

    def __init__(
        self,
        max_fields: int = 10_000,
    ) -> None:
        if max_fields <= 0:
            raise ValueError(
                "max_fields deve ser maior que zero."
            )

        self.max_fields = max_fields

    def parse(
        self,
        file_path: str | Path,
    ) -> JsonAnalysisResult:
        """Adaptador legado; consumidores orquestrados devem usar parse_step."""
        step = self.parse_step(file_path)
        return step.value or JsonAnalysisResult(error_message=step.user_message)

    def parse_step(
        self,
        file_path: str | Path,
    ) -> StepResult[JsonAnalysisResult]:
        path = Path(file_path)

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return self._step(
                ProcessingStatus.SKIPPED,
                "Formato não aplicável à análise JSON.",
            )

        try:
            import forensihash_core

        except ImportError as error:
            return self._failure_step(
                ProcessingStatus.UNAVAILABLE,
                "json_rust_unavailable",
                "O módulo Rust de análise JSON não está disponível.",
                error,
            )

        try:
            raw_result = (
                forensihash_core.parse_json_file(
                    str(path),
                    self.max_fields,
                )
            )

            data = json.loads(raw_result)

        except Exception as error:
            return self._failure_step(
                ProcessingStatus.FAILED,
                "json_parser_failed",
                "O parser JSON não concluiu a análise.",
                error,
            )

        result = self._build_result(data)
        if not result.is_valid:
            issue = ProcessingIssue(
                code="json_invalid",
                status=ProcessingStatus.FAILED,
                technical_message="O conteúdo não representa JSON válido.",
                user_message="O arquivo JSON é inválido.",
                component="json",
                impact=ProcessingImpact.COMPONENT_ONLY,
            )
            return self._step(
                ProcessingStatus.FAILED,
                issue.user_message,
                value=result,
                issues=[issue],
            )
        if result.truncated:
            issue = ProcessingIssue(
                code="json_result_truncated",
                status=ProcessingStatus.PARTIAL,
                technical_message="O limite de campos JSON foi atingido.",
                user_message="A análise JSON foi concluída parcialmente.",
                component="json",
                impact=ProcessingImpact.COMPONENT_ONLY,
            )
            return self._step(
                ProcessingStatus.PARTIAL,
                issue.user_message,
                value=result,
                issues=[issue],
            )
        status = ProcessingStatus.SUCCESS if result.fields else ProcessingStatus.NO_FINDINGS
        return self._step(status, "Análise JSON concluída.", value=result)

    @staticmethod
    def _failure_step(
        status: ProcessingStatus,
        code: str,
        message: str,
        error: BaseException,
    ) -> StepResult[JsonAnalysisResult]:
        issue = ProcessingIssue(
            code=code,
            status=status,
            technical_message=message,
            user_message=message,
            component="json",
            details={"error_type": type(error).__name__},
            impact=ProcessingImpact.COMPONENT_ONLY,
            original_exception=error,
        )
        return JsonParserService._step(
            status,
            message,
            value=JsonAnalysisResult(is_valid=False, error_message=message),
            issues=[issue],
        )

    @staticmethod
    def _step(
        status: ProcessingStatus,
        message: str,
        *,
        value: JsonAnalysisResult | None = None,
        issues: list[ProcessingIssue] | None = None,
    ) -> StepResult[JsonAnalysisResult]:
        return StepResult(
            code="json_analysis",
            component="json",
            status=status,
            technical_message=message,
            user_message=message,
            value=value,
            issues=issues or [],
        )

    def _build_result(
        self,
        data: dict[str, Any],
    ) -> JsonAnalysisResult:
        result = JsonAnalysisResult(
            is_valid=bool(
                data.get("is_valid", False)
            ),
            streaming_used=bool(
                data.get(
                    "streaming_used",
                    False,
                )
            ),
            root_type=str(
                data.get(
                    "root_type",
                    "",
                )
            ),
            total_fields=int(
                data.get(
                    "total_fields",
                    0,
                )
            ),
            displayed_fields=int(
                data.get(
                    "displayed_fields",
                    0,
                )
            ),
            truncated=bool(
                data.get(
                    "truncated",
                    False,
                )
            ),
            error_message=str(
                data.get(
                    "error_message",
                    "",
                )
            ),
        )

        fields = data.get(
            "fields",
            [],
        )

        if not isinstance(fields, list):
            return result

        for item in fields:
            if not isinstance(item, dict):
                continue

            json_field = JsonField(
                path=str(
                    item.get(
                        "path",
                        "",
                    )
                ),
                key=str(
                    item.get(
                        "key",
                        "",
                    )
                ),
                value=item.get("value"),
                value_type=str(
                    item.get(
                        "value_type",
                        "",
                    )
                ),
                category=str(
                    item.get(
                        "category",
                        "other",
                    )
                ),
            )

            result.add_field(json_field)

        return result

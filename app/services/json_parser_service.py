import json
from pathlib import Path
from typing import Any

from app.models.json_analysis_result import (
    JsonAnalysisResult,
    JsonField,
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
        path = Path(file_path)

        if path.suffix.lower() not in self.SUPPORTED_EXTENSIONS:
            return JsonAnalysisResult(
                error_message=(
                    "Extensão JSON não suportada."
                )
            )

        try:
            import forensihash_core

        except ImportError as error:
            return JsonAnalysisResult(
                error_message=(
                    "O módulo Rust forensihash_core não está "
                    "instalado no ambiente virtual. Execute "
                    "'maturin develop' dentro de "
                    "rust/forensihash_core."
                )
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
            return JsonAnalysisResult(
                error_message=str(error)
            )

        return self._build_result(data)

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
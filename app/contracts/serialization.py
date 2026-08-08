from __future__ import annotations

import json
import math
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.contracts.analysis import (
    AnalysisContract,
    AnalysisState,
    ContractError,
    ExternalResult,
    Fact,
    FindingContract,
    Limitation,
    SCHEMA_VERSION,
)


_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "password",
    "secret",
    "token",
    "path",
    "source_path",
    "working_path",
    "original_path",
}


def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Números não finitos não são permitidos no contrato.")
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Datetime do contrato deve conter timezone.")
        return value.isoformat()
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bytes):
        return {"encoding": "hex", "value": value.hex()}
    if is_dataclass(value):
        return json_safe(asdict(value))
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value, key=str):
            normalized = str(key)
            if normalized.lower() in _SENSITIVE_KEYS:
                continue
            result[normalized] = json_safe(value[key])
        return result
    if isinstance(value, (list, tuple, set)):
        items = list(value)
        if isinstance(value, set):
            items.sort(key=repr)
        return [json_safe(item) for item in items]
    raise TypeError(f"Tipo não serializável no contrato: {type(value).__name__}")


class AnalysisContractJson:
    @staticmethod
    def dumps(contract: AnalysisContract, *, indent: int | None = 2) -> str:
        return json.dumps(
            json_safe(contract),
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
            allow_nan=False,
        )

    @staticmethod
    def dump(contract: AnalysisContract, output_path: Path) -> None:
        output_path.write_text(
            AnalysisContractJson.dumps(contract) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def loads(payload: str) -> AnalysisContract:
        data = json.loads(payload)
        if data.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(
                "Versão de schema não suportada: "
                f"{data.get('schema_version')!r}. Esperada: {SCHEMA_VERSION}."
            )
        return AnalysisContract(
            **{
                **data,
                "state": AnalysisState(data["state"]),
                "facts": [Fact(**item) for item in data.get("facts", [])],
                "findings": [
                    FindingContract(**item) for item in data.get("findings", [])
                ],
                "limitations": [
                    Limitation(**item) for item in data.get("limitations", [])
                ],
                "errors": [
                    ContractError(
                        **{
                            **item,
                            "occurred_at": datetime.fromisoformat(item["occurred_at"]),
                        }
                    )
                    for item in data.get("errors", [])
                ],
                "external_results": [
                    ExternalResult(
                        **{
                            **item,
                            "observed_at": datetime.fromisoformat(item["observed_at"]),
                        }
                    )
                    for item in (data.get("external_results") or [])
                ] if data.get("external_results") is not None else None,
            }
        )

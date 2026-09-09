from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path

from app.observability.models import ObservabilitySnapshot
from app.observability.sanitization import safe_ref, sanitize_message, sanitize_metadata


DIAGNOSTIC_SCHEMA_VERSION = "1.1.0"
PERFORMANCE_SCHEMA_VERSION = "1.0.0"


def diagnostic_payload(snapshot: ObservabilitySnapshot) -> dict[str, object]:
    def clean(value, key=""):
        if key == "message":
            return "Mensagem livre omitida no export sanitizado." if value else None
        if key == "rule_id" and isinstance(value, str):
            return safe_ref("rule", value)
        if key == "metadata":
            return sanitize_metadata(dict(value))
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return {
                item.name: clean(
                    getattr(value, "component_id", "Componente")
                    if item.name == "display_name"
                    else getattr(value, item.name),
                    item.name,
                )
                for item in fields(value)
            }
        if hasattr(value, "items"):
            return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [clean(v) for v in value]
        if isinstance(value, str):
            return sanitize_message(value)
        return value

    data = clean(snapshot)
    return {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "performance_schema_version": PERFORMANCE_SCHEMA_VERSION,
        "forensihash_version": snapshot.environment.forensihash_version,
        **data,
    }


def export_diagnostic(snapshot: ObservabilitySnapshot, destination: Path) -> Path:
    destination = Path(destination)
    destination.write_text(
        json.dumps(diagnostic_payload(snapshot), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return destination

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

from app.observability.models import ObservabilitySnapshot


DIAGNOSTIC_SCHEMA_VERSION = "1.0.0"


def diagnostic_payload(snapshot: ObservabilitySnapshot) -> dict[str, object]:
    def clean(value):
        if isinstance(value, Enum): return value.value
        if isinstance(value, datetime): return value.isoformat()
        if isinstance(value, dict): return {str(k): clean(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [clean(v) for v in value]
        return value
    data = clean(asdict(snapshot))
    return {
        "diagnostic_schema_version": DIAGNOSTIC_SCHEMA_VERSION,
        "forensihash_version": snapshot.environment.forensihash_version,
        **data,
    }


def export_diagnostic(snapshot: ObservabilitySnapshot, destination: Path) -> Path:
    destination = Path(destination)
    destination.write_text(json.dumps(diagnostic_payload(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
    return destination

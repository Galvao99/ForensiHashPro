from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True, slots=True)
class FilesystemTimestamp:
    field: str
    operation: str
    raw_seconds: float
    value: datetime | None
    error: OSError | OverflowError | ValueError | None = None


def read_filesystem_timestamp(
    field: str,
    raw_seconds: float,
    *,
    converter: Callable[..., datetime] = datetime.fromtimestamp,
) -> FilesystemTimestamp:
    """Convert a filesystem timestamp without substituting an invented date."""
    operation = f"datetime.fromtimestamp(stat.{field}, tz=timezone.utc)"
    try:
        value = converter(raw_seconds, tz=timezone.utc)
    except (OSError, OverflowError, ValueError) as error:
        return FilesystemTimestamp(field, operation, raw_seconds, None, error)
    return FilesystemTimestamp(field, operation, raw_seconds, value)

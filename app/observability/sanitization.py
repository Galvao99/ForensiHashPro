from __future__ import annotations

import re
from pathlib import Path
from typing import Any


_PATH = re.compile(r"(?:(?:[A-Za-z]:[\\/])|/)[^\s\"']+")
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


def safe_ref(prefix: str, value: object) -> str:
    import hashlib
    digest = hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def sanitize_message(message: object, *, maximum: int = 300) -> str:
    text = str(message).replace("\r", " ").replace("\n", " ")
    text = _PATH.sub("[path]", text)
    text = _EMAIL.sub("[email]", text)
    text = _IP.sub("[ip]", text)
    return text[:maximum]


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    allowed = {"file_type", "extension", "size_bytes", "reason", "capability"}
    return {
        key: value for key, value in metadata.items()
        if key in allowed and isinstance(value, (str, int, float, bool, type(None)))
    }

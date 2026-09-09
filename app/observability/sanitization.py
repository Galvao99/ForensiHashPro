from __future__ import annotations

import re
from typing import Any


_PATH = re.compile(r"(?:(?:[A-Za-z]:[\\/])|/)[^\s\"']+")
_EMAIL = re.compile(r"\b[^\s@]+@[^\s@]+\.[^\s@]+\b")
_IP = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_IPV6 = re.compile(r"(?<![\w:])(?:[0-9a-fA-F]{0,4}:){2,}[0-9a-fA-F:.]{0,39}(?![\w:])")
_CPF = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CNPJ = re.compile(r"\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")
_COORDINATES = re.compile(r"(?<!\d)-?\d{1,3}\.\d{4,}\s*[,;]\s*-?\d{1,3}\.\d{4,}(?!\d)")


def safe_ref(prefix: str, value: object) -> str:
    import hashlib

    digest = hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def sanitize_message(message: object, *, maximum: int = 300) -> str:
    text = str(message).replace("\r", " ").replace("\n", " ")
    text = _EMAIL.sub("[email]", text)
    text = _IP.sub("[ip]", text)
    text = _IPV6.sub("[ip]", text)
    text = _CPF.sub("[cpf]", text)
    text = _CNPJ.sub("[cnpj]", text)
    text = _COORDINATES.sub("[coordinates]", text)
    text = _PATH.sub("[path]", text)
    return text[:maximum]


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, str | int | float | bool | None]:
    # Free-form strings can contain names even after regex redaction. Store only
    # quantities and explicitly recognized operational vocabulary.
    result = {}
    size = metadata.get("size_bytes")
    if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
        result["size_bytes"] = size
    vocabulary = {
        "file_type": {"PDF", "JSON", "IMAGE", "UNKNOWN", "ZIP", "TEXT"},
        "extension": {".pdf", ".json", ".jsonl", ".png", ".jpg", ".jpeg", ".txt", ".zip"},
        "reason": {"capability_not_enabled", "disabled", "unavailable"},
    }
    for key, allowed in vocabulary.items():
        value = metadata.get(key)
        if isinstance(value, str) and value in allowed:
            result[key] = value
    return result


def safe_identifier(value: str) -> str:
    """Keep structural IDs, pseudonymize everything resembling user content."""
    if (
        re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_.:-]{0,95}|\d{1,4}", value)
        and sanitize_message(value) == value
    ):
        return value
    return safe_ref("ref", value)

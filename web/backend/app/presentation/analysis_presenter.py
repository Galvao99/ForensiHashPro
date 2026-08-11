from __future__ import annotations

import re
from pathlib import PurePosixPath
from collections.abc import Mapping
from typing import Any

from app.contracts import AnalysisContract
from app.contracts.serialization import json_safe


_DROP = object()
_NORMALIZE_KEY = re.compile(r"[^a-z0-9]+")
_WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:^|\s)(?:[a-z]:[\\/]|\\\\)[^\s]+")
_POSIX_ABSOLUTE = re.compile(r"(?:^|\s)/(?:tmp|home|root|opt|var|run|etc)/[^\s]+")

_BLOCKED_KEYS = {
    "accessedat",
    "createdat",
    "directory",
    "environment",
    "environ",
    "exception",
    "executablepath",
    "fileaccessdate",
    "fileinodechangedate",
    "filemodifydate",
    "filename",
    "filepermissions",
    "footerbytes",
    "headerbytes",
    "headerpreviewascii",
    "headerpreviewhex",
    "modifiedat",
    "originalpath",
    "path",
    "rawdata",
    "rawpayload",
    "resolvedpath",
    "sourcefile",
    "sourcepath",
    "stacktrace",
    "temporarypath",
    "toolpath",
    "traceback",
    "workingpath",
    "workspace",
}
_SENSITIVE_FRAGMENTS = {
    "apikey",
    "authorization",
    "credential",
    "cookie",
    "password",
    "passwd",
    "secret",
    "token",
}


class AnalysisPresenter:
    """Produz JSON público sem modificar o contrato técnico interno."""

    def present(
        self, contract: AnalysisContract, *, display_name: str | None = None
    ) -> dict[str, Any]:
        value = self._sanitize(json_safe(contract))
        if not isinstance(value, dict):
            raise TypeError("A apresentação de AnalysisContract deve ser um objeto JSON.")
        if display_name is not None and isinstance(value.get("file"), dict):
            value["file"]["name"] = display_name
        if display_name is not None and isinstance(value.get("timeline"), list):
            for record in value["timeline"]:
                if isinstance(record, dict) and record.get("record_type") == "event":
                    record["filename"] = display_name
        raw = json_safe(contract)
        if isinstance(raw, dict):
            self._restore_archive_entry_names(value, raw)
        return value

    @classmethod
    def _restore_archive_entry_names(cls, public: Any, raw: Any) -> None:
        if isinstance(public, dict) and isinstance(raw, Mapping):
            if "embedded_artifact_ref" in public and isinstance(raw.get("filename"), str):
                public["filename"] = PurePosixPath(
                    raw["filename"].replace("\\", "/")
                ).name[:255]
            for key, child in public.items():
                if key in raw:
                    cls._restore_archive_entry_names(child, raw[key])
        elif isinstance(public, list) and isinstance(raw, list):
            for child, raw_child in zip(public, raw):
                cls._restore_archive_entry_names(child, raw_child)

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            sensitive_field = self._describes_sensitive_field(value)
            result: dict[str, Any] = {}
            for key, item in value.items():
                normalized = self._normalized_key(str(key))
                if self._blocked_key(normalized):
                    continue
                if sensitive_field and normalized in {"value", "originalvalue"}:
                    result[str(key)] = "[redacted]"
                    continue
                sanitized = self._sanitize(item)
                if sanitized is not _DROP:
                    result[str(key)] = sanitized
            return result
        if isinstance(value, list):
            return [item for value_item in value if (item := self._sanitize(value_item)) is not _DROP]
        if isinstance(value, str):
            if self._contains_internal_path(value):
                return _DROP
            return value
        return value

    @classmethod
    def _describes_sensitive_field(cls, value: Mapping[Any, Any]) -> bool:
        candidate = value.get("key") or value.get("original_name")
        return isinstance(candidate, str) and cls._blocked_key(cls._normalized_key(candidate))

    @staticmethod
    def _normalized_key(key: str) -> str:
        segment = key.rsplit(":", 1)[-1]
        return _NORMALIZE_KEY.sub("", segment.lower())

    @staticmethod
    def _blocked_key(normalized: str) -> bool:
        return normalized in _BLOCKED_KEYS or any(
            fragment in normalized for fragment in _SENSITIVE_FRAGMENTS
        )

    @staticmethod
    def _contains_internal_path(value: str) -> bool:
        return bool(_WINDOWS_ABSOLUTE.search(value) or _POSIX_ABSOLUTE.search(value))

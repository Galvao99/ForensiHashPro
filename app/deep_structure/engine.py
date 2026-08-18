from __future__ import annotations

import importlib
import json
from pathlib import Path
from typing import Any, Protocol

from .models import StructureReport


class DeepStructureError(RuntimeError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class _NativeSession(Protocol):
    def report_json(self) -> str: ...
    def get_object(self, object_id: str) -> str: ...
    def get_raw_object(self, object_id: str) -> bytes: ...
    def get_raw_stream(self, object_id: str) -> bytes: ...
    def get_decoded_stream(self, object_id: str) -> bytes: ...
    def get_preview(self, object_id: str) -> bytes: ...
    def get_visual_asset(self, object_id: str) -> str: ...
    def get_composite_preview(self, object_id: str) -> bytes: ...
    def get_embedded_file(self, object_id: str) -> bytes: ...
    def get_metadata_text(self, object_id: str) -> str: ...


class DeepStructureSession:
    """Keeps the parsed PDF alive so heavy payloads can be requested without reparsing."""

    def __init__(self, native: _NativeSession) -> None:
        self._native = native
        self.report = StructureReport.from_dict(json.loads(native.report_json()))

    def get_object(self, object_id: str) -> dict[str, Any]:
        return json.loads(self._native.get_object(object_id))

    def get_raw_object(self, object_id: str) -> bytes:
        return bytes(self._native.get_raw_object(object_id))

    def get_raw_stream(self, object_id: str) -> bytes:
        return bytes(self._native.get_raw_stream(object_id))

    def get_decoded_stream(self, object_id: str) -> bytes:
        return bytes(self._native.get_decoded_stream(object_id))

    def get_preview(self, object_id: str) -> bytes:
        return bytes(self._native.get_preview(object_id))

    def get_visual_asset(self, object_id: str) -> dict[str, Any]:
        return json.loads(self._native.get_visual_asset(object_id))

    def get_composite_preview(self, object_id: str) -> bytes:
        return bytes(self._native.get_composite_preview(object_id))

    def get_embedded_file(self, object_id: str) -> bytes:
        return bytes(self._native.get_embedded_file(object_id))

    def get_metadata_text(self, object_id: str) -> str:
        return self._native.get_metadata_text(object_id)


class DeepFileStructureEngine:
    def __init__(self, *, max_file_bytes: int = 512 * 1024 * 1024, max_decoded_stream_bytes: int = 64 * 1024 * 1024,
                 max_preview_width: int = 16_384, max_preview_height: int = 16_384, max_preview_pixels: int = 100_000_000,
                 max_nested_resource_depth: int = 16, max_embedded_file_bytes: int = 128 * 1024 * 1024,
                 max_preview_cache_bytes: int = 128 * 1024 * 1024) -> None:
        limits = (max_file_bytes, max_decoded_stream_bytes, max_preview_width, max_preview_height, max_preview_pixels,
                  max_nested_resource_depth, max_embedded_file_bytes, max_preview_cache_bytes)
        if any(value <= 0 for value in limits):
            raise ValueError("size limits must be greater than zero")
        self.max_file_bytes = max_file_bytes
        self.max_decoded_stream_bytes = max_decoded_stream_bytes
        self.max_preview_width = max_preview_width
        self.max_preview_height = max_preview_height
        self.max_preview_pixels = max_preview_pixels
        self.max_nested_resource_depth = max_nested_resource_depth
        self.max_embedded_file_bytes = max_embedded_file_bytes
        self.max_preview_cache_bytes = max_preview_cache_bytes

    def analyze_pdf(self, path: str | Path) -> DeepStructureSession:
        source = Path(path)
        core: Any = importlib.import_module("forensihash_core")
        try:
            native = core.analyze_pdf(
                str(source), self.max_file_bytes, self.max_decoded_stream_bytes,
                self.max_preview_width, self.max_preview_height, self.max_preview_pixels,
                self.max_nested_resource_depth, self.max_embedded_file_bytes, self.max_preview_cache_bytes,
            )
        except (RuntimeError, ValueError) as error:
            message = str(error)
            normalized = message.lower()
            if "limit" in normalized or "exceeds" in normalized:
                category = "limit_exceeded"
            elif "header not found" in normalized:
                category = "unsupported"
            else:
                category = "malformed"
            raise DeepStructureError(category, message) from error
        return DeepStructureSession(native)


def analyze_pdf(path: str | Path) -> DeepStructureSession:
    return DeepFileStructureEngine().analyze_pdf(path)

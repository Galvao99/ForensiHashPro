from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Protocol

from .models import JpegStructureReport, StructureReport


LOGGER = logging.getLogger("forensihash.deep_structure")


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


class JpegDeepStructureSession:
    """Keeps JPEG source bytes and its stable structural inventory available lazily."""

    def __init__(self, native: Any) -> None:
        self._native = native
        self.report = JpegStructureReport.from_dict(json.loads(native.report_json()))

    def get_segment(self, index: int) -> dict[str, Any]: return json.loads(self._native.get_segment(index))
    def get_segment_raw(self, index: int) -> bytes: return bytes(self._native.get_segment_raw(index))
    def get_scan(self, index: int) -> dict[str, Any]: return json.loads(self._native.get_scan(index))
    def get_scan_raw(self, index: int) -> bytes: return bytes(self._native.get_scan_raw(index))
    def get_exif_ifd(self, path: str) -> dict[str, Any]: return json.loads(self._native.get_exif_ifd(path))
    def get_exif_entry(self, path: str, tag_id: int) -> dict[str, Any]: return json.loads(self._native.get_exif_entry(path, tag_id))
    def get_visual_asset(self, asset_id: str) -> bytes: return bytes(self._native.get_visual_asset(asset_id))
    def get_preview(self, asset_id: str = "jpeg_main") -> bytes: return bytes(self._native.get_preview(asset_id))
    def get_xmp_text(self, packet_id: str) -> str: return self._native.get_xmp_text(packet_id)
    def get_xmp_raw(self, packet_id: str) -> bytes: return bytes(self._native.get_xmp_raw(packet_id))
    def get_icc_profile(self) -> bytes: return bytes(self._native.get_icc_profile())
    def get_trailing_bytes(self) -> bytes: return bytes(self._native.get_trailing_bytes())


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
        except (OSError, RuntimeError, ValueError) as error:
            LOGGER.exception(
                "deep_structure_failed",
                extra={
                    "engine": "deep_structure",
                    "operation": "analyze_pdf",
                    "file": str(source),
                },
            )
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

    def analyze_jpeg(self, path: str | Path, *, max_segments: int = 100_000,
                     max_app_payload_bytes: int = 64 * 1024 * 1024, max_exif_ifds: int = 128,
                     max_exif_entries: int = 100_000, max_exif_depth: int = 16,
                     max_icc_bytes: int = 128 * 1024 * 1024, max_xmp_bytes: int = 64 * 1024 * 1024,
                     max_thumbnail_bytes: int = 64 * 1024 * 1024, max_scans: int = 4096) -> JpegDeepStructureSession:
        limits = (max_segments, max_app_payload_bytes, max_exif_ifds, max_exif_entries, max_exif_depth,
                  max_icc_bytes, max_xmp_bytes, max_thumbnail_bytes, max_scans)
        if any(value <= 0 for value in limits):
            raise ValueError("size limits must be greater than zero")
        core: Any = importlib.import_module("forensihash_core")
        try:
            native = core.analyze_jpeg(str(Path(path)), self.max_file_bytes, *limits)
        except (OSError, RuntimeError, ValueError) as error:
            LOGGER.exception(
                "deep_structure_failed",
                extra={
                    "engine": "deep_structure",
                    "operation": "analyze_jpeg",
                    "file": str(Path(path)),
                },
            )
            message = str(error)
            normalized = message.lower()
            category = (
                "limit_exceeded"
                if "limit" in normalized
                else ("unsupported" if "soi/marker" in normalized else "malformed")
            )
            raise DeepStructureError(category, message) from error
        return JpegDeepStructureSession(native)


def analyze_pdf(path: str | Path) -> DeepStructureSession:
    return DeepFileStructureEngine().analyze_pdf(path)


def analyze_jpeg(path: str | Path) -> JpegDeepStructureSession:
    return DeepFileStructureEngine().analyze_jpeg(path)

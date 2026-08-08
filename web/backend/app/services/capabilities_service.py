from __future__ import annotations

import importlib.util
from typing import Any

from app.settings import ApplicationPaths, SettingsService, ToolDetector


class CapabilitiesService:
    """Expõe disponibilidade operacional sem revelar configuração ou paths."""

    def get(self) -> dict[str, Any]:
        paths = ApplicationPaths.discover()
        settings = SettingsService(paths=paths).load()
        detector = ToolDetector(paths)
        exiftool = detector.exiftool(enabled=settings.metadata_enabled)
        tesseract = detector.tesseract(enabled=settings.ocr_enabled)
        poppler = detector.poppler(enabled=settings.ocr_enabled)
        rust = detector.rust_core(enabled=settings.rust_json_enabled)
        signature_available = importlib.util.find_spec("pyhanko") is not None

        return {
            "hashes": {"available": True},
            "magic_number": {"available": True},
            "metadata": {"available": exiftool.available, "engine": "exiftool"},
            "ocr": {
                "available": tesseract.available and poppler.available,
                "engine": "tesseract",
                "pdf_rendering": poppler.available,
            },
            "pdf_structure": {"available": True},
            "binary_structure": {"available": True},
            "signature": {"available": signature_available},
            "rust_json": {"available": rust.available},
            "biometrics": {"available": True, "formats": ["aware_knomi"]},
            "ip": {
                "available": settings.ip_lookup_enabled and bool(settings.ip_api_key),
                "automatic_in_individual_analysis": False,
            },
            "timeline": {"available_in_individual_analysis": False},
            "comparison": {"available_in_individual_analysis": False},
            "correlation": {"available_in_individual_analysis": False},
        }

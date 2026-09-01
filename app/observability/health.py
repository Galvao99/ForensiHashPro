from __future__ import annotations

from datetime import datetime, timezone

from app.observability.models import ComponentHealth, OperationalStatus
from app.settings import ApplicationPaths, SettingsService, ToolDetector


class HealthCheckService:
    """Checks rápidos de presença/capacidade; nunca abre evidência nem executa análise."""

    def __init__(self, detector: ToolDetector | None = None) -> None:
        self.detector = detector or ToolDetector()

    def run(self) -> tuple[ComponentHealth, ...]:
        now = datetime.now(timezone.utc)
        paths = ApplicationPaths.discover()
        settings = SettingsService(paths=paths).load()
        checks = (
            ("python_runtime", "Python runtime", True, True, None, "Runtime disponível."),
            self._tool("rust_core", "Rust Core", False, self.detector.rust_core(enabled=settings.rust_json_enabled), now),
            self._tool("exiftool", "ExifTool", False, self.detector.exiftool(enabled=settings.metadata_enabled), now),
            self._tool("tesseract", "Tesseract OCR", False, self.detector.tesseract(enabled=settings.ocr_enabled), now),
            self._tool("poppler", "Poppler", False, self.detector.poppler(enabled=settings.ocr_enabled), now),
            ("pdf_structure", "PDF structural parser", True, True, None, "Componente Python disponível."),
            ("digital_signature", "Digital Signature Engine", True, True, None, "Componente Python disponível."),
            ("timeline", "Timeline Engine", True, True, None, "Componente Python disponível."),
            ("correlation", "Correlation Engine", True, True, None, "Componente Python disponível."),
        )
        result = []
        for check in checks:
            if isinstance(check, ComponentHealth):
                result.append(check)
            else:
                component_id, name, required, available, version, message = check
                result.append(ComponentHealth(component_id, name,
                    OperationalStatus.OK if available else OperationalStatus.UNAVAILABLE,
                    now, required, version, message))
        return tuple(result)

    @staticmethod
    def _tool(component_id, name, required, status, now) -> ComponentHealth:
        state = OperationalStatus.OK if status.available else OperationalStatus.UNAVAILABLE
        return ComponentHealth(component_id, name, state, now, required, None,
                               "Disponível." if status.available else "Dependência opcional indisponível ou desabilitada.")

from __future__ import annotations

import importlib.util
import os
import shutil
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

from app.settings.paths import ApplicationPaths, configured_path


class ToolState(str, Enum):
    AVAILABLE = "available"
    NOT_INSTALLED = "not_installed"
    INVALID_PATH = "invalid_path"
    DISABLED = "disabled"


@dataclass(frozen=True, slots=True)
class ToolStatus:
    name: str
    state: ToolState
    path: Path | None
    message: str

    @property
    def available(self) -> bool:
        return self.state is ToolState.AVAILABLE


class ToolUnavailableError(RuntimeError):
    def __init__(self, status: ToolStatus) -> None:
        super().__init__(status.message)
        self.status = status


class ToolDetector:
    """Detecta capacidades locais sem executar ferramentas externas."""

    def __init__(
        self,
        paths: ApplicationPaths | None = None,
        *,
        environ: dict[str, str] | None = None,
        which: Callable[[str], str | None] = shutil.which,
    ) -> None:
        self.paths = paths or ApplicationPaths.discover()
        self.environ = os.environ if environ is None else environ
        self.which = which

    def exiftool(self, *, enabled: bool = True) -> ToolStatus:
        return self._executable(
            name="ExifTool",
            enabled=enabled,
            environment_name="FORENSIHASH_EXIFTOOL_PATH",
            bundled_relative="tools/exiftool/exiftool.exe",
            commands=("exiftool", "exiftool.exe"),
        )

    def tesseract(self, *, enabled: bool = True) -> ToolStatus:
        return self._executable(
            name="Tesseract OCR",
            enabled=enabled,
            environment_name="FORENSIHASH_TESSERACT_PATH",
            bundled_relative="tools/tesseract/tesseract.exe",
            commands=("tesseract", "tesseract.exe"),
        )

    def poppler(self, *, enabled: bool = True) -> ToolStatus:
        configured = configured_path(
            "FORENSIHASH_POPPLER_PATH", environ=self.environ
        )
        if not enabled:
            return self._disabled("Poppler")
        if configured is not None:
            executable = configured / "pdftoppm.exe" if configured.is_dir() else configured
            return self._configured_status("Poppler", configured, executable)

        bundled_dir = self.paths.resource("tools/poppler/bin")
        if (bundled_dir / "pdftoppm.exe").is_file():
            return self._available("Poppler", bundled_dir)

        discovered = self.which("pdftoppm") or self.which("pdftoppm.exe")
        if discovered:
            return self._available("Poppler", Path(discovered).resolve().parent)
        return self._missing("Poppler")

    def rust_core(self, *, enabled: bool = True) -> ToolStatus:
        if not enabled:
            return self._disabled("forensihash_core")
        if importlib.util.find_spec("forensihash_core") is not None:
            return ToolStatus(
                "forensihash_core",
                ToolState.AVAILABLE,
                None,
                "Componente Rust disponível.",
            )
        return self._missing("forensihash_core")

    def _executable(
        self,
        *,
        name: str,
        enabled: bool,
        environment_name: str,
        bundled_relative: str,
        commands: tuple[str, ...],
    ) -> ToolStatus:
        if not enabled:
            return self._disabled(name)
        configured = configured_path(environment_name, environ=self.environ)
        if configured is not None:
            return self._configured_status(name, configured, configured)
        bundled = self.paths.resource(bundled_relative)
        if bundled.is_file():
            return self._available(name, bundled)
        for command in commands:
            discovered = self.which(command)
            if discovered:
                return self._available(name, Path(discovered).resolve())
        return self._missing(name)

    @staticmethod
    def _configured_status(name: str, configured: Path, executable: Path) -> ToolStatus:
        if executable.is_file():
            return ToolDetector._available(name, configured)
        return ToolStatus(
            name,
            ToolState.INVALID_PATH,
            configured,
            f"Caminho configurado para {name} é inválido: {configured}",
        )

    @staticmethod
    def _available(name: str, path: Path) -> ToolStatus:
        return ToolStatus(name, ToolState.AVAILABLE, path, f"{name} disponível.")

    @staticmethod
    def _missing(name: str) -> ToolStatus:
        return ToolStatus(
            name,
            ToolState.NOT_INSTALLED,
            None,
            f"{name} não está instalado ou não foi localizado.",
        )

    @staticmethod
    def _disabled(name: str) -> ToolStatus:
        return ToolStatus(name, ToolState.DISABLED, None, f"{name} está desabilitado.")

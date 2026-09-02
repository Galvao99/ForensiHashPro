from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class ApplicationPaths:
    """Resolve caminhos da aplicação sem depender do diretório atual."""

    application_dir: Path
    resource_dir: Path
    config_dir: Path
    temp_dir: Path
    bundled: bool = False

    @classmethod
    def discover(
        cls,
        *,
        environ: dict[str, str] | None = None,
        module_file: str | Path = __file__,
        executable: str | Path | None = None,
        bundle_dir: str | Path | None = None,
    ) -> ApplicationPaths:
        env = os.environ if environ is None else environ
        detected_bundle = bundle_dir or getattr(sys, "_MEIPASS", None)
        bundled = detected_bundle is not None

        if bundled:
            resource_dir = Path(detected_bundle).resolve()
            application_dir = Path(
                executable or sys.executable
            ).resolve().parent
        else:
            application_dir = Path(module_file).resolve().parents[2]
            resource_dir = application_dir

        configured_dir = env.get("FORENSIHASH_CONFIG_DIR", "").strip()
        if configured_dir:
            config_dir = Path(configured_dir).expanduser().resolve()
        elif bundled:
            local_data = env.get("LOCALAPPDATA", "").strip()
            base = Path(local_data) if local_data else Path.home() / ".config"
            config_dir = (base / "ForensiHashPro").resolve()
        else:
            config_dir = (application_dir / "config").resolve()

        configured_temp = env.get("FORENSIHASH_TEMP_DIR", "").strip()
        temp_base = (
            Path(configured_temp).expanduser()
            if configured_temp
            else Path(tempfile.gettempdir()) / "ForensiHashPro"
        )

        return cls(
            application_dir=application_dir,
            resource_dir=resource_dir,
            config_dir=config_dir,
            temp_dir=temp_base.resolve(),
            bundled=bundled,
        )

    def resource(self, relative_path: str | Path) -> Path:
        relative = Path(relative_path)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("O caminho do recurso deve ser relativo e seguro.")
        return (self.resource_dir / relative).resolve()

    @property
    def settings_file(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def recent_cases_file(self) -> Path:
        return self.config_dir / "recent_cases.json"


def configured_path(
    environment_name: str,
    *,
    environ: dict[str, str] | None = None,
) -> Path | None:
    env = os.environ if environ is None else environ
    value = env.get(environment_name, "").strip()
    return Path(value).expanduser().resolve() if value else None

import json
import os
from pathlib import Path
from typing import Any, Mapping

from app.settings.paths import ApplicationPaths
from app.settings.settings_model import AppSettings, InvalidConfigurationError
from app.settings.processing_limits import ProcessingLimits


class SettingsService:
    def __init__(
        self,
        settings_path: str | Path | None = None,
        *,
        environ: Mapping[str, str] | None = None,
        paths: ApplicationPaths | None = None,
    ) -> None:
        resolved_paths = paths or ApplicationPaths.discover()
        self.settings_path = (
            Path(settings_path).expanduser().resolve()
            if settings_path is not None
            else resolved_paths.settings_file
        )
        self.environ = os.environ if environ is None else environ

    def load(self) -> AppSettings:
        data: dict[str, Any] = {}
        if self.settings_path.exists():
            try:
                with self.settings_path.open("r", encoding="utf-8") as file:
                    loaded = json.load(file)
            except (OSError, json.JSONDecodeError) as error:
                raise InvalidConfigurationError(
                    f"Não foi possível ler a configuração: {error}"
                ) from error
            if not isinstance(loaded, dict):
                raise InvalidConfigurationError(
                    "A configuração local deve ser um objeto JSON."
                )
            data = loaded

        api_key = self.environ.get("IP2LOCATION_API_KEY", "").strip()
        local_ip_enabled = self._boolean(
            data.get("ip_lookup_enabled"),
            default=bool(api_key),
            name="ip_lookup_enabled",
        )
        local_ocr_enabled = self._boolean(
            data.get("ocr_enabled"), default=True, name="ocr_enabled"
        )
        local_metadata_enabled = self._boolean(
            data.get("metadata_enabled"), default=True, name="metadata_enabled"
        )
        local_rust_enabled = self._boolean(
            data.get("rust_json_enabled"), default=True, name="rust_json_enabled"
        )
        limits_data = data.get("limits", {})
        if not isinstance(limits_data, dict):
            raise InvalidConfigurationError("limits deve ser um objeto JSON.")
        defaults = ProcessingLimits()
        limit_values: dict[str, int] = {}
        for name in defaults.__dataclass_fields__:
            limit_values[name] = self._integer(
                limits_data.get(name, getattr(defaults, name)),
                f"limits.{name}",
            )
        settings = AppSettings(
            theme_mode=str(data.get("theme_mode", "light")).strip().lower(),
            ip_provider=str(data.get("ip_provider", "ip2location")),
            ip_api_key=api_key,
            ip_lookup_enabled=self._boolean(
                self.environ.get("IP2LOCATION_ENABLED"),
                default=local_ip_enabled,
                name="IP2LOCATION_ENABLED",
            ),
            request_timeout=self._integer(
                data.get("request_timeout", 15), "request_timeout"
            ),
            ocr_enabled=self._boolean(
                self.environ.get("FORENSIHASH_OCR_ENABLED"),
                default=local_ocr_enabled,
                name="FORENSIHASH_OCR_ENABLED",
            ),
            metadata_enabled=self._boolean(
                self.environ.get("FORENSIHASH_METADATA_ENABLED"),
                default=local_metadata_enabled,
                name="FORENSIHASH_METADATA_ENABLED",
            ),
            rust_json_enabled=self._boolean(
                self.environ.get("FORENSIHASH_RUST_JSON_ENABLED"),
                default=local_rust_enabled,
                name="FORENSIHASH_RUST_JSON_ENABLED",
            ),
            sidebar_groups=self._sidebar_groups(data.get("sidebar_groups")),
            limits=ProcessingLimits(**limit_values),
        )
        settings.validate()
        return settings

    @staticmethod
    def _sidebar_groups(value: object) -> dict[str, bool]:
        defaults = {"case": True, "file": True, "tools": True}
        if not isinstance(value, dict):
            return defaults
        return {
            key: raw if isinstance(raw, bool) else defaults[key]
            for key, raw in ((key, value.get(key, default)) for key, default in defaults.items())
        }

    def save(self, settings: AppSettings) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

        with self.settings_path.open("w", encoding="utf-8") as file:
            json.dump(
                settings.safe_dict(),
                file,
                ensure_ascii=False,
                indent=4,
            )

    def update_ip_api_key(self, api_key: str) -> AppSettings:
        settings = self.load()
        settings.ip_api_key = api_key.strip()
        settings.ip_lookup_enabled = bool(settings.ip_api_key)
        settings.validate()
        return settings

    @staticmethod
    def _integer(value: object, name: str) -> int:
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise InvalidConfigurationError(f"{name} deve ser inteiro.") from error

    @staticmethod
    def _boolean(value: object, *, default: bool, name: str) -> bool:
        if value is None or value == "":
            return default
        if isinstance(value, bool):
            return value
        normalized = str(value).strip().lower()
        if normalized in {"1", "true", "yes", "sim", "on"}:
            return True
        if normalized in {"0", "false", "no", "não", "nao", "off"}:
            return False
        raise InvalidConfigurationError(
            f"{name} deve ser true/false, 1/0, yes/no ou sim/não."
        )

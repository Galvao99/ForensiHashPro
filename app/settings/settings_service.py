import json
from dataclasses import asdict
from pathlib import Path

from app.settings.settings_model import AppSettings


class SettingsService:
    def __init__(self, settings_path: str | Path = "config/settings.json") -> None:
        self.settings_path = Path(settings_path)

    def load(self) -> AppSettings:
        if not self.settings_path.exists():
            settings = AppSettings()
            self.save(settings)
            return settings

        with self.settings_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        return AppSettings(
            ip_provider=data.get("ip_provider", "ip2location"),
            ip_api_key=data.get("ip_api_key", ""),
            request_timeout=int(data.get("request_timeout", 15)),
        )

    def save(self, settings: AppSettings) -> None:
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)

        with self.settings_path.open("w", encoding="utf-8") as file:
            json.dump(
                asdict(settings),
                file,
                ensure_ascii=False,
                indent=4,
            )

    def update_ip_api_key(self, api_key: str) -> AppSettings:
        settings = self.load()
        settings.ip_api_key = api_key.strip()
        self.save(settings)
        return settings
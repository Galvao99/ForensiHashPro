from datetime import datetime
from typing import Any

from PySide6.QtWidgets import QListWidget

from app.models import AnalysisResult


class TimelineList(QListWidget):
    """Lista simples de eventos temporais da análise."""

    DATE_KEYS = (
        "CreateDate",
        "ModifyDate",
        "MetadataDate",
        "DateTimeOriginal",
        "GPSDateTime",
        "FileModifyDate",
        "FileCreateDate",
        "FileAccessDate",
    )

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelineList")

    def update_timeline(self, result: AnalysisResult) -> None:
        self.clear()

        self.addItem(
            f"Análise realizada: {result.analyzed_at.strftime('%d/%m/%Y %H:%M:%S')}"
        )

        events: list[str] = []

        for key, value in result.metadata.raw.items():
            if self._is_date_key(key):
                events.append(f"{key}: {value}")

        if not events:
            self.addItem("Nenhuma data relevante encontrada nos metadados.")
            return

        for event in events:
            self.addItem(event)

    def _is_date_key(self, key: str) -> bool:
        key_lower = key.lower()
        return any(date_key.lower() in key_lower for date_key in self.DATE_KEYS)
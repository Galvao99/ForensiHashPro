from __future__ import annotations

from collections import Counter
from datetime import datetime
from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QWidget

from app.widgets.technical_timeline import TechnicalTimeline, TimelineSidePanel


class TimelinePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelinePage")

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(14)

        title = QLabel("Linha do Tempo Forense")
        title.setObjectName("TimelinePageTitle")

        subtitle = QLabel(
            "Eventos extraídos do arquivo e metadados associados, organizados cronologicamente."
        )
        subtitle.setObjectName("TimelinePageSubtitle")

        body = QHBoxLayout()
        body.setSpacing(14)

        self.timeline = TechnicalTimeline()
        self.side_panel = TimelineSidePanel()

        body.addWidget(self.timeline, stretch=3)
        body.addWidget(self.side_panel, stretch=1)

        root.addWidget(title)
        root.addWidget(subtitle)
        root.addLayout(body, stretch=1)

    def update_analysis(self, analysis_result) -> None:
        results = self._normalize_results(analysis_result)

        events = []
        for result in results:
            events.extend(self._extract_events(result))

        events = sorted(
            events,
            key=lambda e: self._parse_date(e.get("timestamp")) or datetime.max,
        )

        self.timeline.update_events(events)
        self.side_panel.update_summary(events)

    def update_result(self, analysis_result) -> None:
        self.update_analysis(analysis_result)

    def _normalize_results(self, analysis_result) -> list:
        if analysis_result is None:
            return []

        if isinstance(analysis_result, list):
            return analysis_result

        if isinstance(analysis_result, tuple):
            return list(analysis_result)

        for attr in ["results", "files", "analysis_results"]:
            if hasattr(analysis_result, attr):
                value = getattr(analysis_result, attr)
                if isinstance(value, list):
                    return value

        return [analysis_result]

    def _extract_events(self, result) -> list[dict]:
        ready_events = (
            getattr(result, "timeline_events", None)
            or getattr(result, "timeline", None)
            or getattr(result, "technical_timeline", None)
        )

        if ready_events:
            return [self._event_to_dict(event, result) for event in ready_events]

        metadata = (
            getattr(result, "metadata_result", None)
            or getattr(result, "metadata", None)
        )

        metadata_dict = self._metadata_to_dict(metadata)

        if not metadata_dict and hasattr(result, "__dict__"):
            metadata_dict = result.__dict__

        file_name = self._extract_file_name(result)

        creator = self._find_key(
            metadata_dict,
            ["Creator", "PDF:Creator", "XMP:CreatorTool", "CreatorTool"],
        )

        producer = self._find_key(
            metadata_dict,
            ["Producer", "PDF:Producer"],
        )

        create_date = self._find_key(
            metadata_dict,
            ["CreateDate", "PDF:CreateDate", "XMP:CreateDate", "CreationDate"],
        )

        modify_date = self._find_key(
            metadata_dict,
            ["ModifyDate", "PDF:ModifyDate", "XMP:ModifyDate", "ModDate"],
        )

        events = []

        if create_date:
            events.append(
                {
                    "timestamp": str(create_date),
                    "title": "Documento Criado",
                    "description": file_name,
                    "details": creator or producer or "Criador não identificado",
                    "category": "Criação",
                    "event_type": "creation",
                    "source": "Metadados PDF",
                }
            )

        if modify_date:
            events.append(
                {
                    "timestamp": str(modify_date),
                    "title": "Documento Modificado",
                    "description": file_name,
                    "details": producer or creator or "Producer não identificado",
                    "category": "Modificação",
                    "event_type": "modification",
                    "source": "Metadados PDF/XMP",
                }
            )

        signature = (
            getattr(result, "digital_signature_result", None)
            or getattr(result, "signature_result", None)
            or getattr(result, "digital_signature", None)
        )

        if signature:
            signature_dict = self._metadata_to_dict(signature)
            signed_at = self._find_key(
                signature_dict,
                ["signing_time", "signed_at", "signature_date", "timestamp"],
            )

            if signed_at:
                events.append(
                    {
                        "timestamp": str(signed_at),
                        "title": "Assinatura Digital Aplicada",
                        "description": "Documento assinado digitalmente.",
                        "details": self._find_key(
                            signature_dict,
                            ["issuer", "subject", "certificate"],
                        )
                        or "Certificado identificado",
                        "category": "Assinatura",
                        "event_type": "signature",
                        "source": "PKCS#7",
                    }
                )

        analyzed_at = (
            getattr(result, "analysis_date", None)
            or getattr(result, "analyzed_at", None)
            or getattr(result, "created_at", None)
        )

        if analyzed_at:
            events.append(
                {
                    "timestamp": str(analyzed_at),
                    "title": "Análise Realizada",
                    "description": "Arquivo analisado pelo ForensiHash Pro.",
                    "details": "Engine local",
                    "category": "Sistema",
                    "event_type": "system",
                    "source": "ForensiHash Pro",
                }
            )

        return events

    def _event_to_dict(self, event, result=None) -> dict:
        if isinstance(event, dict):
            return event

        return {
            "timestamp": str(
                getattr(event, "timestamp", None)
                or getattr(event, "date", "")
            ),
            "title": str(
                getattr(event, "title", None)
                or getattr(event, "name", "Evento técnico")
            ),
            "description": str(
                getattr(event, "description", None)
                or getattr(event, "message", "")
            ),
            "details": str(getattr(event, "details", "")),
            "category": str(
                getattr(event, "category", None)
                or getattr(event, "event_type", "Evento")
            ),
            "event_type": str(getattr(event, "event_type", "info")),
            "source": str(getattr(event, "source", "ForensiHash")),
        }

    def _metadata_to_dict(self, metadata) -> dict:
        if metadata is None:
            return {}

        if isinstance(metadata, dict):
            return metadata

        for attr in ["metadata", "raw_metadata", "data", "fields"]:
            if hasattr(metadata, attr):
                value = getattr(metadata, attr)
                if isinstance(value, dict):
                    return value

        if hasattr(metadata, "__dict__"):
            data = metadata.__dict__

            for value in data.values():
                if isinstance(value, dict):
                    return value

            return data

        return {}

    def _find_key(self, data: dict, keys: list[str]):
        if not isinstance(data, dict):
            return None

        for key in keys:
            if key in data and data[key]:
                return data[key]

        for existing_key, value in data.items():
            normalized = str(existing_key).lower()

            for wanted in keys:
                clean = wanted.lower().replace("pdf:", "").replace("xmp:", "")
                if clean in normalized and value:
                    return value

        return None

    def _extract_file_name(self, result) -> str:
        for attr in ["file_name", "filename", "name"]:
            if hasattr(result, attr):
                return str(getattr(result, attr))

        file_info = getattr(result, "file_info", None)

        if file_info:
            for attr in ["file_name", "filename", "name", "path"]:
                if hasattr(file_info, attr):
                    return str(getattr(file_info, attr))

        return "arquivo analisado"

    def _parse_date(self, value):
        if not value:
            return None

        text = str(value).replace("Z", "+00:00")

        for fmt in [
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ]:
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
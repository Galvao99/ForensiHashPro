from __future__ import annotations

import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.models import AnalysisResult
from app.models.timeline_event import TimelineEvent, TimelineResult, TimelineWarning
from app.services.contract_date_extractor import ContractDateExtractor
from app.services.contract_date_selector import ContractDateSelector
from app.services.temporal_parser import ParsedTimestamp, TemporalParser


_TEMPORAL_METADATA = {
    "creationdate": ("creation", "CreationDate"),
    "createdate": ("creation", "CreateDate"),
    "modifydate": ("modification", "ModifyDate"),
    "moddate": ("modification", "ModDate"),
    "metadatadate": ("metadata", "MetadataDate"),
    "filemodifydate": ("filesystem_metadata", "FileModifyDate"),
    "filecreatedate": ("filesystem_metadata", "FileCreateDate"),
    "datetimeoriginal": ("capture", "DateTimeOriginal"),
    "datetimecreated": ("creation", "DateTimeCreated"),
}
_JSON_TEMPORAL_KEY = re.compile(
    r"(?:^|[_\-.])(timestamp|datetime|date|time|created_at|updated_at|occurred_at|event_time)(?:$|[_\-.])",
    re.IGNORECASE,
)


class TimelineService:
    """Constroi a Timeline somente a partir dos resultados ja produzidos."""

    def __init__(self) -> None:
        self.parser = TemporalParser()
        self.date_extractor = ContractDateExtractor()
        self.date_selector = ContractDateSelector()

    def build(self, result: AnalysisResult) -> TimelineResult:
        evidence_ref = self._evidence_ref(result)
        events: list[TimelineEvent] = []
        limitations: list[str] = []
        events.extend(self._metadata_events(result, evidence_ref))
        events.extend(self._contract_events(result, evidence_ref))
        events.extend(self._signature_events(result, evidence_ref))
        events.extend(self._json_events(result, evidence_ref))
        structural, structural_limits = self._pdf_events(result, evidence_ref)
        events.extend(structural)
        limitations.extend(structural_limits)
        events.extend(self._filesystem_events(result, evidence_ref))
        events.extend(self._operational_events(result, evidence_ref))
        events.sort(key=self._sort_key)
        return TimelineResult(
            evidence_ref=evidence_ref,
            events=events,
            warnings=self._warnings(events, evidence_ref),
            limitations=list(dict.fromkeys(limitations)),
        )

    def build_timeline(self, result: AnalysisResult) -> tuple[list[TimelineEvent], str]:
        """API legada mantida para paginas e extensoes existentes."""
        timeline = self.build(result)
        summary = (
            f"{len(timeline.temporal_events)} evento(s) temporal(is), "
            f"{len(timeline.structural_events)} evento(s) estrutural(is) e "
            f"{len(timeline.warnings)} warning(s) tecnico(s)."
        )
        return timeline.events, summary

    def _metadata_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for raw_key, value in result.metadata.raw.items():
            group, field_name = self._field_parts(str(raw_key))
            definition = _TEMPORAL_METADATA.get(self._compact(field_name))
            parsed = self.parser.parse(value)
            if definition is None or parsed is None:
                continue
            event_type, canonical = definition
            source_type = "filesystem_metadata" if event_type.startswith("filesystem") else "metadata"
            events.append(self._temporal_event(
                evidence_ref=evidence_ref, filename=result.file_info.name,
                event_type=event_type, category="metadata", title=canonical,
                description=f"{canonical} registrado no campo {raw_key}.",
                parsed=parsed, source_type=source_type, source_engine="metadata_engine",
                field_path=str(raw_key), attributes={"metadata_group": group, "field": field_name},
            ))
        return events

    def _contract_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        candidates = self.date_extractor.extract(result.extracted_text or "")
        selected = self.date_selector.select(candidates)
        selected_candidate = selected.extracted_date if selected else None
        source = self._text_source(result)
        events: list[TimelineEvent] = []
        for candidate in candidates:
            parsed = self.parser.parse(candidate.raw_text)
            if parsed is None:
                parsed = self.parser.parse(candidate.value)
            if parsed is None:
                continue
            is_contract = selected_candidate is candidate
            events.append(self._temporal_event(
                evidence_ref=evidence_ref, filename=result.file_info.name,
                event_type="contract_date" if is_contract else "text_date",
                category="contract" if is_contract else "text",
                title="Data contratual" if is_contract else "Data identificada no texto",
                description=(
                    "Data selecionada pelo contexto contratual disponível."
                    if is_contract else "Data textual sem papel contratual confirmado."
                ),
                parsed=parsed, source_type=source, source_engine="contract_date_extractor",
                offset=candidate.start, context=candidate.context,
                attributes={"range": [candidate.start, candidate.end], "format": candidate.format.value},
                confidence=(min(1.0, max(0.0, selected.score / 12)) if is_contract else None),
                limitations=("A classificação depende do contexto textual extraído.",) if is_contract else (),
            ))
        return events

    def _signature_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        signature = result.digital_signature
        definitions = (
            ("signing_time", "signature", "Signing Time declarado", "Momento de assinatura declarado no objeto de assinatura."),
            ("timestamp", "timestamp_token", "Timestamp da assinatura", "Timestamp técnico associado à assinatura."),
            ("valid_from", "certificate_validity", "Certificate NotBefore", "Início da validade do certificado; não representa o momento da assinatura."),
            ("valid_until", "certificate_validity", "Certificate NotAfter", "Fim da validade do certificado; não representa o momento da assinatura."),
        )
        events: list[TimelineEvent] = []
        for field_name, event_type, title, description in definitions:
            parsed = self.parser.parse(getattr(signature, field_name, None))
            if parsed is None:
                continue
            limitations = ()
            if field_name == "signing_time":
                limitations = ("O horário é autodeclarado e não equivale a validação criptográfica independente.",)
            events.append(self._temporal_event(
                evidence_ref=evidence_ref, filename=result.file_info.name,
                event_type=event_type, category="signature", title=title,
                description=description, parsed=parsed, source_type="digital_signature",
                source_engine="digital_signature_engine", field_path=field_name,
                limitations=limitations,
            ))
        return events

    def _json_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        analysis = result.json_analysis
        if analysis is None:
            return []
        events: list[TimelineEvent] = []
        for item in getattr(analysis, "fields", ()):
            if not (_JSON_TEMPORAL_KEY.search(item.key) or item.category.lower() in {"date", "datetime", "timestamp", "temporal"}):
                continue
            if isinstance(item.value, (int, float)):
                continue
            parsed = self.parser.parse(item.value)
            if parsed is None:
                continue
            events.append(self._temporal_event(
                evidence_ref=evidence_ref, filename=result.file_info.name,
                event_type="json_event", category="json", title=f"Evento JSON: {item.key}",
                description=f"Timestamp registrado no campo JSON {item.path}.", parsed=parsed,
                source_type="json", source_engine="json_engine", field_path=item.path,
                attributes={"key": item.key},
            ))
        return events

    def _filesystem_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for field_name, value, event_type, title in (
            ("created_at", result.file_info.created_at, "filesystem_created", "Criação no filesystem"),
            ("modified_at", result.file_info.modified_at, "filesystem_modified", "Modificação no filesystem"),
            ("accessed_at", result.file_info.accessed_at, "filesystem_accessed", "Acesso no filesystem"),
        ):
            parsed = self.parser.parse(value)
            if parsed:
                events.append(self._temporal_event(
                    evidence_ref=evidence_ref, filename=result.file_info.name,
                    event_type=event_type, category="filesystem", title=title,
                    description="Timestamp da identidade de filesystem adquirida para a evidência.",
                    parsed=parsed, source_type="filesystem", source_engine="evidence_manager",
                    field_path=field_name,
                    limitations=("Este timestamp do filesystem é distinto dos metadados internos do documento.",),
                ))
        return events

    def _operational_events(self, result: AnalysisResult, evidence_ref: str) -> list[TimelineEvent]:
        events: list[TimelineEvent] = []
        for event_type, title, value in (
            ("analysis_started", "Análise iniciada", result.analyzed_at),
            ("analysis_finished", "Análise finalizada", result.completed_at),
        ):
            parsed = self.parser.parse(value)
            if parsed:
                events.append(self._temporal_event(
                    evidence_ref=evidence_ref, filename=result.file_info.name,
                    event_type=event_type, category="operational", title=title,
                    description="Evento operacional do ForensiHash; não integra a história documental.",
                    parsed=parsed, source_type="processing", source_engine="analysis_service",
                ))
        return events

    def _pdf_events(self, result: AnalysisResult, evidence_ref: str) -> tuple[list[TimelineEvent], list[str]]:
        raw = getattr(result.binary_analysis, "pdf_raw_analysis", None)
        structure = result.pdf_structure
        if raw is None and structure is None:
            return [], []
        count = max(
            1,
            len(raw.startxrefs) if raw else 0,
            len(raw.eof_offsets) if raw else 0,
            (structure.incremental_updates + 1) if structure else 0,
        )
        events: list[TimelineEvent] = []
        for index in range(count):
            startxref = raw.startxrefs[index] if raw and index < len(raw.startxrefs) else None
            declared = startxref.declared_offset if startxref else None
            xref_type = self._xref_type(raw, declared)
            attributes: dict[str, Any] = {
                "xref_type": xref_type,
                "startxref_offset": startxref.marker_offset if startxref else None,
                "startxref_declared_offset": declared,
                "eof_offset": raw.eof_offsets[index] if raw and index < len(raw.eof_offsets) else None,
                "trailer_offset": raw.trailer_offsets[index] if raw and index < len(raw.trailer_offsets) else None,
                "prev": raw.prev_offsets[index - 1] if raw and index > 0 and index - 1 < len(raw.prev_offsets) else None,
            }
            attributes = {key: value for key, value in attributes.items() if value is not None}
            title = "PDF Revision #1" if index == 0 else f"Incremental Update #{index}"
            event_type = "pdf_revision" if index == 0 else "pdf_incremental_update"
            offset = declared if declared is not None else attributes.get("eof_offset")
            events.append(self._structural_event(
                evidence_ref, result.file_info.name, event_type, title,
                "Revisão estrutural identificada pelos marcadores já extraídos do PDF.",
                index + 1, offset, attributes,
            ))
        limitations = []
        if count > 1:
            limitations.append(
                "A estrutura atual não associa com segurança todos os objetos e trailers a cada revisão PDF."
            )
        return events, limitations

    def _warnings(self, events: list[TimelineEvent], evidence_ref: str) -> list[TimelineWarning]:
        creations = [item for item in events if item.category == "metadata" and item.event_type == "creation"]
        modifications = [item for item in events if item.category == "metadata" and item.event_type == "modification"]
        warnings: list[TimelineWarning] = []
        for creation in creations:
            for modification in modifications:
                if creation.attributes.get("metadata_group") != modification.attributes.get("metadata_group"):
                    continue
                left, right = creation.date, modification.date
                if left is None or right is None or (left.tzinfo is None) != (right.tzinfo is None):
                    continue
                if modification.precision not in {"day", "minute", "second", "millisecond", "microsecond"}:
                    continue
                if creation.precision not in {"day", "minute", "second", "millisecond", "microsecond"}:
                    continue
                if right < left:
                    warnings.append(TimelineWarning(
                        warning_id=self._id(evidence_ref, "temporal_order_inconsistency", creation.event_id, modification.event_id),
                        rule_id="metadata_modify_before_creation", severity="warning",
                        title="Ordem temporal inconsistente",
                        description="ModifyDate é anterior a CreationDate segundo os valores registrados nos metadados.",
                        evidence_ref=evidence_ref, event_ids=(creation.event_id, modification.event_id),
                    ))
        return warnings

    def _temporal_event(
        self, *, evidence_ref: str, filename: str, event_type: str, category: str,
        title: str, description: str, parsed: ParsedTimestamp, source_type: str,
        source_engine: str, page: int | None = None, offset: int | None = None,
        field_path: str | None = None, context: str | None = None,
        attributes: dict[str, Any] | None = None, confidence: float | None = None,
        limitations: tuple[str, ...] = (),
    ) -> TimelineEvent:
        attributes = dict(attributes or {})
        if parsed.utc_normalized:
            attributes["utc_normalized"] = parsed.utc_normalized
        event_id = self._id(evidence_ref, event_type, field_path or "", str(offset), parsed.raw)
        return TimelineEvent(
            event_id=event_id, event_type=event_type, category=category, title=title,
            description=description, timestamp=parsed.normalized, raw_timestamp=parsed.raw,
            timezone=parsed.timezone_name, timezone_status=parsed.timezone_status,
            precision=parsed.precision, source_type=source_type, source_engine=source_engine,
            evidence_ref=evidence_ref, filename=filename, temporal_status=parsed.temporal_status,
            page=page, offset=offset, field_path=field_path, context=context,
            attributes=attributes, confidence=confidence, limitations=limitations,
        )

    def _structural_event(
        self, evidence_ref: str, filename: str, event_type: str, title: str,
        description: str, sequence: int, offset: int | None, attributes: dict[str, Any],
    ) -> TimelineEvent:
        return TimelineEvent(
            event_id=self._id(evidence_ref, event_type, str(sequence), str(offset)),
            event_type=event_type, category="pdf_structure", title=title,
            description=description, timestamp=None, raw_timestamp=None, timezone=None,
            timezone_status="not_applicable", precision=None, source_type="pdf_structure",
            source_engine="binary_structure_engine", evidence_ref=evidence_ref,
            filename=filename, temporal_status="structural_only", offset=offset,
            revision=sequence, structural_sequence=sequence, attributes=attributes,
        )

    @staticmethod
    def _xref_type(raw: Any, declared: int | None) -> str | None:
        if raw is None or declared is None:
            return None
        if declared in raw.xref_stream_offsets:
            return "xref_stream"
        if declared in raw.xref_offsets:
            return "traditional_xref"
        return None

    @staticmethod
    def _field_parts(key: str) -> tuple[str, str]:
        if ":" in key:
            return tuple(key.split(":", 1))  # type: ignore[return-value]
        return "unknown", key

    @staticmethod
    def _compact(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    @staticmethod
    def _text_source(result: AnalysisResult) -> str:
        for step in reversed(result.processing_steps):
            if step.code == "text_extraction" and step.value is not None:
                return str(getattr(step.value, "source", "text"))
        return "text"

    @staticmethod
    def _evidence_ref(result: AnalysisResult) -> str:
        if result.evidence_source is not None:
            return result.evidence_source.evidence_id
        return str(uuid5(NAMESPACE_URL, f"forensihash:evidence:{result.hashes.sha256}"))

    @staticmethod
    def _id(evidence_ref: str, *parts: str) -> str:
        return str(uuid5(NAMESPACE_URL, ":".join(("forensihash", "timeline", evidence_ref, *parts))))

    @staticmethod
    def _sort_key(event: TimelineEvent) -> tuple[int, object, int, str]:
        temporal_key = event.temporal_order_key
        if temporal_key is not None:
            return 0, temporal_key, event.structural_sequence or 0, event.event_id
        return 1, (2, (), ""), event.structural_sequence or 0, event.event_id

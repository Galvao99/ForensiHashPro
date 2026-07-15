from datetime import datetime
from typing import Any, Sequence

from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.models import AnalysisResult
from app.services.contract_date_extractor import ContractDateExtractor
from app.services.contract_date_selector import ContractDateSelector


class InvestigationContextBuilder:
    """
    Consolida os resultados individuais em um único contexto
    para execução das regras investigativas.

    O builder apenas organiza informações já extraídas.
    Ele não executa OCR, consultas externas ou análise forense.
    """

    PRODUCER_KEYS = (
        "Producer",
        "PDF:Producer",
        "XMP:Producer",
    )

    CREATOR_KEYS = (
        "Creator",
        "PDF:Creator",
        "XMP:CreatorTool",
        "CreatorTool",
        "Software",
    )

    METADATA_DATE_KEYS = (
        "CreateDate",
        "PDF:CreateDate",
        "XMP:CreateDate",
        "FileCreateDate",
        "CreationDate",
        "ModifyDate",
        "PDF:ModifyDate",
        "XMP:ModifyDate",
        "FileModifyDate",
        "ModDate",
    )

    def __init__(
        self,
        contract_date_extractor: ContractDateExtractor | None = None,
        contract_date_selector: ContractDateSelector | None = None,
    ) -> None:
        self.contract_date_extractor = (
            contract_date_extractor or ContractDateExtractor()
        )
        self.contract_date_selector = (
            contract_date_selector or ContractDateSelector()
        )

    def build(
        self,
        results: Sequence[AnalysisResult],
    ) -> InvestigationContext:
        context = InvestigationContext(
            results=list(results),
        )

        for result in results:
            evidence_key = str(
                result.file_info.path.resolve()
            )

            context.display_names[evidence_key] = (
                result.file_info.name
            )

            self._populate_extracted_text(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_hashes(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_contract_date(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_metadata(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_signature(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_timeline(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_ip_data(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_json_data(
                context=context,
                result=result,
                file_name=evidence_key,
            )

        # ESTE RETURN É ESSENCIAL.
        return context

    # ==============================================================
    # TEXTO / OCR
    # ==============================================================

    def _populate_extracted_text(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        text = self._extract_text(result)

        if text:
            context.extracted_texts[file_name] = text

    def _extract_text(
        self,
        result: AnalysisResult,
    ) -> str:
        possible_attributes = (
            "extracted_text",
            "ocr_text",
            "text",
            "content_text",
            "full_text",
        )

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            if isinstance(value, str) and value.strip():
                return value.strip()

        ocr_result = getattr(
            result,
            "ocr_result",
            None,
        )

        if ocr_result is not None:
            for attribute in possible_attributes:
                value = getattr(
                    ocr_result,
                    attribute,
                    None,
                )

                if isinstance(value, str) and value.strip():
                    return value.strip()

        return ""

    # ==============================================================
    # HASHES
    # ==============================================================

    def _populate_hashes(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        hashes = self._extract_hashes(result)

        if hashes:
            context.calculated_hashes[file_name] = hashes

    def _extract_hashes(
        self,
        result: AnalysisResult,
    ) -> dict[str, str]:
        hash_result = (
            getattr(result, "hashes", None)
            or getattr(result, "hash_result", None)
        )

        if hash_result is None:
            return {}

        hash_attributes = (
            ("MD5", "md5"),
            ("SHA-1", "sha1"),
            ("SHA-224", "sha224"),
            ("SHA-256", "sha256"),
            ("SHA-384", "sha384"),
            ("SHA-512", "sha512"),
        )

        hashes: dict[str, str] = {}

        for algorithm, attribute in hash_attributes:
            value = getattr(
                hash_result,
                attribute,
                None,
            )

            if value:
                hashes[algorithm] = (
                    str(value)
                    .strip()
                    .lower()
                )

        values = getattr(
            hash_result,
            "values",
            None,
        )

        if isinstance(values, dict):
            for algorithm, value in values.items():
                if not value:
                    continue

                hashes[str(algorithm).upper()] = (
                    str(value)
                    .strip()
                    .lower()
                )

        return hashes

    # ==============================================================
    # DATA CONTRATUAL
    # ==============================================================

    def _populate_contract_date(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        contract_date = self._extract_contract_date(
            result
        )

        if contract_date is not None:
            context.contract_dates[file_name] = (
                contract_date
            )

    def _extract_contract_date(
        self,
        result: AnalysisResult,
    ) -> datetime | None:
        possible_attributes = (
            "contract_date",
            "agreement_date",
            "signing_date",
            "document_date",
        )

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            parsed = self._parse_date(value)

            if parsed is not None:
                return parsed

        text = self._extract_text(result)

        if not text:
            return None

        extracted_dates = self.contract_date_extractor.extract(text)
        candidate = self.contract_date_selector.select(extracted_dates)

        if candidate is None:
            return None

        return candidate.extracted_date.value

    # ==============================================================
    # METADADOS / PRODUCER / CREATOR
    # ==============================================================

    def _populate_metadata(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        metadata_values = self._extract_metadata_values(
            result
        )

        if not metadata_values:
            return

        context.metadata_values[file_name] = (
            metadata_values
        )

        metadata_dates = (
            self._extract_metadata_dates(
                metadata_values
            )
        )

        if metadata_dates:
            context.metadata_dates[file_name] = (
                metadata_dates
            )

        producer = self._find_first_metadata_value(
            metadata_values,
            self.PRODUCER_KEYS,
        )

        if producer:
            context.producers[file_name] = producer

        creator = self._find_first_metadata_value(
            metadata_values,
            self.CREATOR_KEYS,
        )

        if creator:
            context.creators[file_name] = creator

    def _extract_metadata_values(
        self,
        result: AnalysisResult,
    ) -> dict[str, Any]:
        metadata_result = getattr(
            result,
            "metadata",
            None,
        )

        if metadata_result is None:
            return {}

        raw = getattr(
            metadata_result,
            "raw",
            None,
        )

        if isinstance(raw, dict):
            return dict(raw)

        legacy_metadata = getattr(
            metadata_result,
            "metadata",
            None,
        )

        if isinstance(legacy_metadata, dict):
            return dict(legacy_metadata)

        if isinstance(metadata_result, dict):
            return dict(metadata_result)

        return {}

    def _extract_metadata_dates(
        self,
        metadata_values: dict[str, Any],
    ) -> dict[str, datetime]:
        dates: dict[str, datetime] = {}

        for key in self.METADATA_DATE_KEYS:
            value = metadata_values.get(key)
            parsed = self._parse_date(value)

            if parsed is not None:
                dates[key] = parsed

        return dates

    def _find_first_metadata_value(
        self,
        metadata_values: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str:
        for key in keys:
            value = metadata_values.get(key)

            if value is None:
                continue

            normalized = str(value).strip()

            if normalized:
                return normalized

        return ""

    # ==============================================================
    # ASSINATURA DIGITAL
    # ==============================================================

    def _populate_signature(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        signature_result = getattr(
            result,
            "digital_signature",
            None,
        )

        if signature_result is not None:
            context.signature_results[file_name] = (
                signature_result
            )

    # ==============================================================
    # TIMELINE
    # ==============================================================

    def _populate_timeline(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        timeline_events = getattr(
            result,
            "timeline_events",
            None,
        )

        if isinstance(timeline_events, list):
            context.timeline_events[file_name] = list(
                timeline_events
            )

    # ==============================================================
    # IP
    # ==============================================================

    def _populate_ip_data(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        detected_ips = self._extract_detected_ips(
            result
        )

        if detected_ips:
            context.detected_ips[file_name] = (
                detected_ips
            )

        ip_results = self._extract_ip_results(
            result
        )

        if ip_results:
            context.ip_results[file_name] = (
                ip_results
            )

    def _extract_detected_ips(
        self,
        result: AnalysisResult,
    ) -> list[str]:
        possible_attributes = (
            "detected_ips",
            "ips",
            "ip_addresses",
        )

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            if isinstance(value, list):
                return list(
                    dict.fromkeys(
                        str(item).strip()
                        for item in value
                        if str(item).strip()
                    )
                )

        return []

    def _extract_ip_results(
        self,
        result: AnalysisResult,
    ) -> list[Any]:
        possible_attributes = (
            "ip_results",
            "ip_lookup_results",
            "enriched_ips",
        )

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            if isinstance(value, list):
                return list(value)

        return []

    # ==============================================================
    # JSON / RUST
    # ==============================================================

    def _populate_json_data(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        json_analysis = getattr(
            result,
            "json_analysis",
            None,
        )

        if json_analysis is None:
            return

        context.json_results[file_name] = (
            json_analysis
        )

    # ==============================================================
    # DATAS
    # ==============================================================

    def _parse_date(
        self,
        value: Any,
    ) -> datetime | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()

        if not text:
            return None

        normalized_text = text.replace(
            "Z",
            "+00:00",
        )

        try:
            return datetime.fromisoformat(
                normalized_text
            )

        except ValueError:
            pass

        known_formats = (
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
            "%Y%m%d%H%M%S%z",
            "%Y%m%d%H%M%SZ",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%d/%m/%Y",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y",
        )

        for date_format in known_formats:
            try:
                return datetime.strptime(
                    text,
                    date_format,
                )

            except ValueError:
                continue

        return None

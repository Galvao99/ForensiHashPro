from datetime import datetime
from typing import Any, Sequence

from app.investigation.investigation_context import InvestigationContext
from app.models import AnalysisResult


class InvestigationContextBuilder:
    """
    Constrói um contexto consolidado para a CorrelationEngine.

    O builder centraliza a extração dos resultados técnicos para
    evitar que cada regra precise navegar diretamente pelo
    AnalysisResult.
    """

    TEXT_ATTRIBUTES = (
        "text",
        "ocr_text",
        "extracted_text",
        "content_text",
        "full_text",
    )

    DATE_KEYS = (
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

    def build(
        self,
        results: Sequence[AnalysisResult],
    ) -> InvestigationContext:
        context = InvestigationContext(
            results=list(results),
        )

        for result in results:
            file_name = result.file_info.name

            self._populate_text(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_hashes(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_contract_date(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_metadata(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_ip_data(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_signature_data(
                context=context,
                result=result,
                file_name=file_name,
            )

            self._populate_timeline_data(
                context=context,
                result=result,
                file_name=file_name,
            )

        return context

    # ------------------------------------------------------------------
    # Preenchimento do contexto
    # ------------------------------------------------------------------

    def _populate_text(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        text = self._extract_text(result)

        if text:
            context.extracted_texts[file_name] = text

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

    def _populate_contract_date(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        contract_date = self._extract_contract_date(result)

        if contract_date:
            context.contract_dates[file_name] = contract_date

    def _populate_metadata(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        metadata_values = self._extract_metadata_values(result)

        if not metadata_values:
            return

        context.metadata_values[file_name] = metadata_values

        metadata_dates = self._extract_metadata_dates(
            metadata_values
        )

        if metadata_dates:
            context.metadata_dates[file_name] = metadata_dates

        producer = self._find_first_metadata_value(
            metadata=metadata_values,
            keys=self.PRODUCER_KEYS,
        )

        if producer:
            context.producers[file_name] = producer

        creator = self._find_first_metadata_value(
            metadata=metadata_values,
            keys=self.CREATOR_KEYS,
        )

        if creator:
            context.creators[file_name] = creator

    def _populate_ip_data(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        detected_ips = self._extract_detected_ips(result)

        if detected_ips:
            context.detected_ips[file_name] = detected_ips

        ip_results = self._extract_ip_results(result)

        if ip_results:
            context.ip_results[file_name] = ip_results

    def _populate_signature_data(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        signature_result = self._extract_signature_result(result)

        if signature_result is not None:
            context.signature_results[file_name] = signature_result

    def _populate_timeline_data(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        timeline_events = self._extract_timeline_events(result)

        if timeline_events:
            context.timeline_events[file_name] = timeline_events

    # ------------------------------------------------------------------
    # Texto
    # ------------------------------------------------------------------

    def _extract_text(
        self,
        result: AnalysisResult,
    ) -> str:
        direct_text = self._find_text_in_object(result)

        if direct_text:
            return direct_text

        ocr_result = getattr(result, "ocr_result", None)

        if ocr_result is not None:
            ocr_text = self._find_text_in_object(ocr_result)

            if ocr_text:
                return ocr_text

        text_result = getattr(
            result,
            "text_extraction_result",
            None,
        )

        if text_result is not None:
            extracted_text = self._find_text_in_object(
                text_result
            )

            if extracted_text:
                return extracted_text

        return ""

    def _find_text_in_object(
        self,
        target: Any,
    ) -> str:
        for attr in self.TEXT_ATTRIBUTES:
            value = getattr(target, attr, None)

            if isinstance(value, str) and value.strip():
                return value.strip()

        return ""

    # ------------------------------------------------------------------
    # Hashes
    # ------------------------------------------------------------------

    def _extract_hashes(
        self,
        result: AnalysisResult,
    ) -> dict[str, str]:
        hash_result = (
            getattr(result, "hash_result", None)
            or getattr(result, "hashes", None)
        )

        if hash_result is None:
            return {}

        hashes: dict[str, str] = {}

        known_attributes = (
            "md5",
            "sha1",
            "sha224",
            "sha256",
            "sha384",
            "sha512",
        )

        for attr in known_attributes:
            value = getattr(hash_result, attr, None)

            if value:
                algorithm = self._format_hash_algorithm(attr)

                hashes[algorithm] = str(value).strip().lower()

        values = getattr(hash_result, "values", None)

        if isinstance(values, dict):
            for algorithm, value in values.items():
                if not value:
                    continue

                formatted_algorithm = self._format_hash_algorithm(
                    str(algorithm)
                )

                hashes[formatted_algorithm] = (
                    str(value).strip().lower()
                )

        if isinstance(hash_result, dict):
            for algorithm, value in hash_result.items():
                if not value:
                    continue

                formatted_algorithm = self._format_hash_algorithm(
                    str(algorithm)
                )

                hashes[formatted_algorithm] = (
                    str(value).strip().lower()
                )

        return hashes

    def _format_hash_algorithm(
        self,
        algorithm: str,
    ) -> str:
        normalized = algorithm.strip().upper().replace("_", "-")

        aliases = {
            "SHA1": "SHA-1",
            "SHA224": "SHA-224",
            "SHA256": "SHA-256",
            "SHA384": "SHA-384",
            "SHA512": "SHA-512",
        }

        return aliases.get(normalized, normalized)

    # ------------------------------------------------------------------
    # Data contratual
    # ------------------------------------------------------------------

    def _extract_contract_date(
        self,
        result: AnalysisResult,
    ) -> datetime | None:
        possible_values = (
            getattr(result, "contract_date", None),
            getattr(result, "contract_datetime", None),
            getattr(result, "document_date", None),
        )

        for value in possible_values:
            parsed = self._parse_date(value)

            if parsed:
                return parsed

        return None

    # ------------------------------------------------------------------
    # Metadados
    # ------------------------------------------------------------------

    def _extract_metadata_values(
        self,
        result: AnalysisResult,
    ) -> dict[str, Any]:
        metadata_result = (
            getattr(result, "metadata", None)
            or getattr(result, "metadata_result", None)
        )

        if metadata_result is None:
            return {}

        if isinstance(metadata_result, dict):
            return dict(metadata_result)

        possible_attributes = (
            "metadata",
            "values",
            "raw",
            "data",
        )

        for attr in possible_attributes:
            value = getattr(metadata_result, attr, None)

            if isinstance(value, dict):
                return dict(value)

        return {}

    def _extract_metadata_dates(
        self,
        metadata_values: dict[str, Any],
    ) -> dict[str, datetime]:
        dates: dict[str, datetime] = {}

        for key in self.DATE_KEYS:
            parsed = self._parse_date(
                metadata_values.get(key)
            )

            if parsed:
                dates[key] = parsed

        return dates

    def _find_first_metadata_value(
        self,
        *,
        metadata: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str:
        for key in keys:
            value = metadata.get(key)

            if value is None:
                continue

            normalized = str(value).strip()

            if normalized:
                return normalized

        return ""

    # ------------------------------------------------------------------
    # IP
    # ------------------------------------------------------------------

    def _extract_detected_ips(
        self,
        result: AnalysisResult,
    ) -> list[str]:
        possible_attributes = (
            "detected_ips",
            "ips",
            "ip_addresses",
        )

        for attr in possible_attributes:
            value = getattr(result, attr, None)

            normalized = self._normalize_ip_list(value)

            if normalized:
                return normalized

        ip_result = getattr(result, "ip_result", None)

        if ip_result is not None:
            for attr in possible_attributes:
                value = getattr(ip_result, attr, None)

                normalized = self._normalize_ip_list(value)

                if normalized:
                    return normalized

        return []

    def _normalize_ip_list(
        self,
        value: Any,
    ) -> list[str]:
        if isinstance(value, str):
            normalized = value.strip()

            return [normalized] if normalized else []

        if not isinstance(value, (list, tuple, set)):
            return []

        ips: list[str] = []

        for item in value:
            if isinstance(item, str):
                normalized = item.strip()

            else:
                normalized = str(
                    getattr(item, "ip", "")
                ).strip()

            if normalized and normalized not in ips:
                ips.append(normalized)

        return ips

    def _extract_ip_results(
        self,
        result: AnalysisResult,
    ) -> list[Any]:
        possible_attributes = (
            "ip_results",
            "ip_lookup_results",
            "ip_analysis_results",
        )

        for attr in possible_attributes:
            value = getattr(result, attr, None)

            if isinstance(value, list):
                return list(value)

        ip_result = getattr(result, "ip_result", None)

        if isinstance(ip_result, list):
            return list(ip_result)

        if ip_result is not None:
            return [ip_result]

        return []

    # ------------------------------------------------------------------
    # Assinatura digital
    # ------------------------------------------------------------------

    def _extract_signature_result(
        self,
        result: AnalysisResult,
    ) -> Any | None:
        possible_attributes = (
            "digital_signature_result",
            "signature_result",
            "signature",
            "digital_signature",
        )

        for attr in possible_attributes:
            value = getattr(result, attr, None)

            if value is not None:
                return value

        return None

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    def _extract_timeline_events(
        self,
        result: AnalysisResult,
    ) -> list[Any]:
        possible_attributes = (
            "timeline_events",
            "timeline",
            "events",
        )

        for attr in possible_attributes:
            value = getattr(result, attr, None)

            if isinstance(value, list):
                return list(value)

        timeline_result = getattr(
            result,
            "timeline_result",
            None,
        )

        if timeline_result is not None:
            events = getattr(
                timeline_result,
                "events",
                None,
            )

            if isinstance(events, list):
                return list(events)

        return []

    # ------------------------------------------------------------------
    # Datas
    # ------------------------------------------------------------------

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

        normalized_text = self._normalize_timezone_text(text)

        known_formats = (
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%Y%m%d%H%M%SZ",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
        )

        for date_format in known_formats:
            try:
                return datetime.strptime(
                    normalized_text,
                    date_format,
                )
            except ValueError:
                continue

        try:
            return datetime.fromisoformat(normalized_text)
        except ValueError:
            return None

    def _normalize_timezone_text(
        self,
        value: str,
    ) -> str:
        text = value.strip()

        if text.endswith("Z"):
            return f"{text[:-1]}+0000"

        if len(text) >= 6:
            timezone_part = text[-6:]

            if (
                timezone_part[0] in {"+", "-"}
                and timezone_part[3] == ":"
            ):
                return (
                    f"{text[:-6]}"
                    f"{timezone_part[:3]}"
                    f"{timezone_part[4:]}"
                )

        return text
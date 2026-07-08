from datetime import datetime
from typing import Any, Sequence

from app.investigation.investigation_context import InvestigationContext
from app.models import AnalysisResult


class InvestigationContextBuilder:
    """
    Monta um contexto único para a CorrelationEngine.
    """

    def build(
        self,
        results: Sequence[AnalysisResult],
    ) -> InvestigationContext:
        context = InvestigationContext(
            results=list(results),
        )

        for result in results:
            file_name = result.file_info.name

            # Texto extraído
            text = self._extract_text(result)
            if text:
                context.extracted_texts[file_name] = text

            # Hashes calculados
            hashes = self._extract_hashes(result)
            if hashes:
                context.calculated_hashes[file_name] = hashes

            # Data de pactuação
            contract_date = self._extract_contract_date(result)
            if contract_date:
                context.contract_dates[file_name] = contract_date

            # Datas dos metadados
            metadata_dates = self._extract_metadata_dates(result)
            if metadata_dates:
                context.metadata_dates[file_name] = metadata_dates

            # Resultados de IP (quando existirem)
            ip_results = self._extract_ip_results(result)
            if ip_results:
                context.raw.setdefault("ip_results", []).extend(ip_results)

        return context

    def _extract_text(self, result: AnalysisResult) -> str:
        for attr in (
            "text",
            "ocr_text",
            "extracted_text",
            "content_text",
            "full_text",
        ):
            value = getattr(result, attr, None)

            if isinstance(value, str) and value.strip():
                return value

        ocr_result = getattr(result, "ocr_result", None)

        if ocr_result is not None:
            for attr in (
                "text",
                "ocr_text",
                "extracted_text",
                "content_text",
                "full_text",
            ):
                value = getattr(ocr_result, attr, None)

                if isinstance(value, str) and value.strip():
                    return value

        return ""

    def _extract_hashes(self, result: AnalysisResult) -> dict[str, str]:
        hash_result = (
            getattr(result, "hash_result", None)
            or getattr(result, "hashes", None)
        )

        if hash_result is None:
            return {}

        hashes: dict[str, str] = {}

        for attr in ("md5", "sha1", "sha256", "sha512"):
            value = getattr(hash_result, attr, None)

            if value:
                hashes[attr.upper()] = str(value).lower()

        values = getattr(hash_result, "values", None)

        if isinstance(values, dict):
            for algorithm, value in values.items():
                if value:
                    hashes[str(algorithm).upper()] = str(value).lower()

        return hashes

    def _extract_contract_date(
        self,
        result: AnalysisResult,
    ) -> datetime | None:
        value = getattr(result, "contract_date", None)

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            return self._parse_date(value)

        return None

    def _extract_metadata_dates(
        self,
        result: AnalysisResult,
    ) -> dict[str, datetime]:
        metadata = getattr(result, "metadata", None)

        if metadata is None:
            return {}

        data: dict[str, Any] = getattr(metadata, "metadata", {}) or {}

        date_keys = (
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

        dates: dict[str, datetime] = {}

        for key in date_keys:
            parsed = self._parse_date(data.get(key))

            if parsed:
                dates[key] = parsed

        return dates

    def _extract_ip_results(
        self,
        result: AnalysisResult,
    ) -> list:
        possible_attrs = (
            "ip_results",
            "ips",
            "ip_lookup_results",
            "detected_ips",
        )

        for attr in possible_attrs:
            value = getattr(result, attr, None)

            if isinstance(value, list):
                return value

        return []

    def _parse_date(
        self,
        value: Any,
    ) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()

        known_formats = (
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y%m%d%H%M%SZ",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
        )

        for fmt in known_formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None
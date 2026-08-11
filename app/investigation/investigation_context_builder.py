import ipaddress

from datetime import datetime
from typing import Any, Sequence

from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.models import AnalysisResult
from app.services.contract_date_extractor import ContractDateExtractor
from app.services.contract_date_selector import ContractDateSelector
from app.models.detected_ip import (
    DetectedIp,
    IpClassification,
)
from app.services.ip_extraction_service import (
    IpExtractionService,
)
from app.entities.service import EntityExtractionService
from app.investigation.declared_hash import DeclaredHashExtractor


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
        ip_extraction_service: IpExtractionService | None = None,
        entity_extraction_service: EntityExtractionService | None = None,
        declared_hash_extractor: DeclaredHashExtractor | None = None,
    ) -> None:
        self.contract_date_extractor = (
            contract_date_extractor
            or ContractDateExtractor()
        )

        self.contract_date_selector = (
            contract_date_selector
            or ContractDateSelector()
        )

        self.ip_extraction_service = (
            ip_extraction_service
            or IpExtractionService()
        )
        self.entity_extraction_service = (
            entity_extraction_service or EntityExtractionService()
        )
        self.declared_hash_extractor = declared_hash_extractor or DeclaredHashExtractor()

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

            self._populate_entities(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_hashes(
                context=context,
                result=result,
                file_name=evidence_key,
            )

            self._populate_declared_hashes(
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

    def _populate_entities(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        entities = list(getattr(result, "resolved_entities", ()) or ())
        if not entities:
            text = self._extract_text(result)
            if text:
                entities = list(
                    self.entity_extraction_service.resolve_legacy_text(
                        text, source_file=file_name
                    ).entities
                )
        if entities:
            context.resolved_entities[file_name] = entities

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

    def _populate_declared_hashes(
        self,
        *,
        context: InvestigationContext,
        result: AnalysisResult,
        file_name: str,
    ) -> None:
        evidence_source = getattr(result, "evidence_source", None)
        evidence_ref = evidence_source.evidence_id if evidence_source is not None else file_name
        filename = result.file_info.name
        occurrences = []
        text_step = next(
            (step for step in reversed(getattr(result, "processing_steps", ()) or ()) if step.code == "text_extraction"),
            None,
        )
        text_result = getattr(text_step, "value", None)
        segments = list(getattr(text_result, "segments", ()) or ())
        if segments:
            for segment in segments:
                occurrences.extend(self.declared_hash_extractor.extract_text(
                    segment.text,
                    evidence_ref=evidence_ref,
                    filename=filename,
                    source_type=segment.source,
                    page=segment.page,
                ))
        else:
            text = self._extract_text(result)
            if text:
                occurrences.extend(self.declared_hash_extractor.extract_text(
                    text,
                    evidence_ref=evidence_ref,
                    filename=filename,
                    source_type="legacy_text",
                ))
        json_analysis = getattr(result, "json_analysis", None)
        if json_analysis is not None:
            for field in (getattr(json_analysis, "fields", ()) or ()):
                occurrences.extend(self.declared_hash_extractor.extract_json_field(
                    field.value,
                    evidence_ref=evidence_ref,
                    filename=filename,
                    field_path=field.path,
                ))
        if occurrences:
            context.declared_hashes[file_name] = occurrences

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
        """
        Consolida IPs estruturados e IPs encontrados no texto/OCR.

        Nenhuma consulta externa é executada nesta etapa.
        """

        structured_addresses = self._extract_detected_ips(
            result
        )

        text = self._extract_text(result)

        text_occurrences = (
            self.ip_extraction_service.extract(text)
            if text
            else []
        )

        structured_occurrences = (
            self._build_structured_ip_details(
                structured_addresses
            )
        )

        all_occurrences = self._merge_ip_occurrences(
            structured_occurrences=structured_occurrences,
            text_occurrences=text_occurrences,
        )

        unique_addresses = list(
            dict.fromkeys(
                occurrence.address
                for occurrence in all_occurrences
            )
        )

        if unique_addresses:
            context.detected_ips[file_name] = (
                unique_addresses
            )

        if all_occurrences:
            context.detected_ip_details[file_name] = (
                all_occurrences
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
        """
        Obtém IPs já estruturados no AnalysisResult.
        """

        possible_attributes = (
            "detected_ips",
            "ips",
            "ip_addresses",
        )

        collected: list[str] = []

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            if not isinstance(
                value,
                (list, tuple, set),
            ):
                continue

            for item in value:
                address = self._extract_ip_address_value(
                    item
                )

                if address:
                    collected.append(address)

        return list(
            dict.fromkeys(collected)
        )


    def _extract_ip_address_value(
        self,
        value: Any,
    ) -> str:
        """
        Extrai e normaliza um endereço IP de string ou objeto.
        """

        if value is None:
            return ""

        if isinstance(value, str):
            candidate = value.strip()

        else:
            candidate = ""

            for attribute in (
                "address",
                "ip",
                "ip_address",
            ):
                attribute_value = getattr(
                    value,
                    attribute,
                    None,
                )

                if attribute_value:
                    candidate = str(
                        attribute_value
                    ).strip()
                    break

        if not candidate:
            return ""

        try:
            parsed = ipaddress.ip_address(
                candidate
            )
        except ValueError:
            return ""

        return self._normalize_ip_address(
            parsed
        )


    def _build_structured_ip_details(
        self,
        addresses: list[str],
    ) -> list[DetectedIp]:
        """
        Converte IPs estruturados em objetos DetectedIp.

        Como não vieram do texto, start/end recebem -1.
        """

        details: list[DetectedIp] = []

        for address in addresses:
            try:
                parsed = ipaddress.ip_address(
                    address
                )
            except ValueError:
                continue

            normalized = self._normalize_ip_address(
                parsed
            )

            details.append(
                DetectedIp(
                    address=normalized,
                    raw_text=address,
                    version=parsed.version,
                    classification=self._classify_ip_address(
                        parsed
                    ),
                    start=-1,
                    end=-1,
                    context=(
                        "Endereço IP previamente estruturado "
                        "no resultado da análise."
                    ),
                )
            )

        return details


    def _merge_ip_occurrences(
        self,
        *,
        structured_occurrences: list[DetectedIp],
        text_occurrences: list[DetectedIp],
    ) -> list[DetectedIp]:
        """
        Preserva ocorrências distintas do texto, mas não cria uma
        ocorrência artificial estruturada quando o mesmo endereço
        já foi encontrado no OCR/texto.
        """

        text_addresses = {
            occurrence.address
            for occurrence in text_occurrences
        }

        merged = [
            occurrence
            for occurrence in structured_occurrences
            if occurrence.address not in text_addresses
        ]

        merged.extend(text_occurrences)

        return sorted(
            merged,
            key=lambda occurrence: (
                occurrence.start < 0,
                occurrence.start
                if occurrence.start >= 0
                else 0,
                occurrence.address,
            ),
        )


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


    @staticmethod
    def _normalize_ip_address(
        address: (
            ipaddress.IPv4Address
            | ipaddress.IPv6Address
        ),
    ) -> str:
        if isinstance(
            address,
            ipaddress.IPv6Address,
        ):
            return address.compressed.lower()

        return str(address)


    def _classify_ip_address(
        self,
        address: (
            ipaddress.IPv4Address
            | ipaddress.IPv6Address
        ),
    ) -> IpClassification:
        if address.is_unspecified:
            return IpClassification.UNSPECIFIED

        if address.is_loopback:
            return IpClassification.LOOPBACK

        if address.is_link_local:
            return IpClassification.LINK_LOCAL

        if address.is_multicast:
            return IpClassification.MULTICAST

        if (
            isinstance(
                address,
                ipaddress.IPv4Address,
            )
            and address
            in self.ip_extraction_service.CGNAT_NETWORK
        ):
            return IpClassification.CGNAT

        if address.is_private:
            return IpClassification.PRIVATE

        if address.is_reserved:
            return IpClassification.RESERVED

        return IpClassification.PUBLIC


    def _extract_detected_ips(
        self,
        result: AnalysisResult,
    ) -> list[str]:
        """
        Obtém endereços IP previamente estruturados no resultado.

        Também aceita objetos que possuam atributos como address ou ip.
        """

        possible_attributes = (
            "detected_ips",
            "ips",
            "ip_addresses",
        )

        collected: list[str] = []

        for attribute in possible_attributes:
            value = getattr(
                result,
                attribute,
                None,
            )

            if not isinstance(
                value,
                (list, tuple, set),
            ):
                continue

            for item in value:
                address = self._extract_ip_address_value(
                    item
                )

                if address:
                    collected.append(address)

        return list(
            dict.fromkeys(collected)
        )


    def _extract_ip_address_value(
        self,
        value: Any,
    ) -> str:
        """
        Normaliza uma representação estruturada de endereço IP.
        """

        if value is None:
            return ""

        if isinstance(value, str):
            candidate = value.strip()

        else:
            candidate = ""

            for attribute in (
                "address",
                "ip",
                "ip_address",
            ):
                attribute_value = getattr(
                    value,
                    attribute,
                    None,
                )

                if attribute_value:
                    candidate = str(
                        attribute_value
                    ).strip()
                    break

        if not candidate:
            return ""

        try:
            parsed = ipaddress.ip_address(
                candidate
            )
        except ValueError:
            return ""

        if isinstance(
            parsed,
            ipaddress.IPv6Address,
        ):
            return parsed.compressed.lower()

        return str(parsed)


    def _build_structured_ip_details(
        self,
        addresses: list[str],
    ) -> list[DetectedIp]:
        """
        Converte IPs previamente estruturados em DetectedIp.

        Como eles não vieram diretamente do OCR, não possuem posição
        ou trecho textual conhecido.
        """

        details: list[DetectedIp] = []

        for address in addresses:
            try:
                parsed = ipaddress.ip_address(
                    address
                )
            except ValueError:
                continue

            details.append(
                DetectedIp(
                    address=self._normalize_ip_address(
                        parsed
                    ),
                    raw_text=address,
                    version=parsed.version,
                    classification=(
                        self._classify_ip_address(
                            parsed
                        )
                    ),
                    start=-1,
                    end=-1,
                    context=(
                        "Endereço IP previamente estruturado "
                        "no resultado da análise."
                    ),
                )
            )

        return details


    def _merge_ip_occurrences(
        self,
        structured_occurrences: list[DetectedIp],
        text_occurrences: list[DetectedIp],
    ) -> list[DetectedIp]:
        """
        Combina resultados estruturados e ocorrências do OCR.

        Ocorrências textuais repetidas são preservadas porque indicam
        posições distintas no documento.

        A ocorrência estruturada é removida quando o mesmo endereço
        também foi encontrado diretamente no texto, evitando criar uma
        ocorrência artificial adicional.
        """

        text_addresses = {
            occurrence.address
            for occurrence in text_occurrences
        }

        merged = [
            occurrence
            for occurrence in structured_occurrences
            if occurrence.address not in text_addresses
        ]

        merged.extend(
            text_occurrences
        )

        return sorted(
            merged,
            key=lambda occurrence: (
                occurrence.start < 0,
                occurrence.start
                if occurrence.start >= 0
                else 0,
                occurrence.address,
            ),
        )


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


    def _normalize_ip_address(
        self,
        address: (
            ipaddress.IPv4Address
            | ipaddress.IPv6Address
        ),
    ) -> str:
        if isinstance(
            address,
            ipaddress.IPv6Address,
        ):
            return address.compressed.lower()

        return str(address)


    def _classify_ip_address(
        self,
        address: (
            ipaddress.IPv4Address
            | ipaddress.IPv6Address
        ),
    ) -> IpClassification:
        """
        Mantém a mesma ordem de classificação utilizada pelo
        IpExtractionService.
        """

        if address.is_unspecified:
            return IpClassification.UNSPECIFIED

        if address.is_loopback:
            return IpClassification.LOOPBACK

        if address.is_link_local:
            return IpClassification.LINK_LOCAL

        if address.is_multicast:
            return IpClassification.MULTICAST

        if (
            isinstance(
                address,
                ipaddress.IPv4Address,
            )
            and address
            in self.ip_extraction_service.CGNAT_NETWORK
        ):
            return IpClassification.CGNAT

        if address.is_private:
            return IpClassification.PRIVATE

        if address.is_reserved:
            return IpClassification.RESERVED

        return IpClassification.PUBLIC

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

from __future__ import annotations

import re
from collections import OrderedDict

from app.entities.models import (
    EntityCandidate,
    EntitySource,
    EntitySourceType,
)
from app.services.contract_date_extractor import ContractDateExtractor
from app.services.ip_extraction_service import IpExtractionService


class CandidateExtractor:
    """Localiza possibilidades; nenhum padrão confirma o tipo da entidade."""

    EMAIL = re.compile(r"(?<![\w@])[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+(?![\w@])")
    MONEY = re.compile(r"(?<!\w)R\$\s*(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?!\d)", re.IGNORECASE)
    DECIMAL = re.compile(r"(?<![\d.,])(?:\d{1,3}(?:\.\d{3})+|\d+),\d{2}(?![\d,])")
    ISO_DATETIME = re.compile(
        r"(?<!\d)\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:[.,]\d+)?)?(?:Z|[+-]\d{2}:\d{2})?)?(?!\d)"
    )
    MASKED_CPF = re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")
    FORMATTED_PHONE = re.compile(
        r"(?<!\d)(?:\+?55[\s.-]?)?\(?\d{2}\)?[\s.-]?(?:9\d{4}|[2-5]\d{3})[\s.-]?\d{4}(?!\d)"
    )
    BARE_NUMERIC = re.compile(r"(?<!\d)\d{5,14}(?!\d)")

    def __init__(
        self,
        *,
        context_radius: int = 80,
        ip_extractor: IpExtractionService | None = None,
        date_extractor: ContractDateExtractor | None = None,
    ) -> None:
        self.context_radius = context_radius
        self.ip_extractor = ip_extractor or IpExtractionService(context_radius=context_radius)
        self.date_extractor = date_extractor or ContractDateExtractor(context_radius=context_radius)

    def extract_text(
        self,
        text: str,
        *,
        source_type: EntitySourceType,
        source_file: str,
        page: int | None = None,
        extractor: str = "candidate_regex_v2",
        base_offset: int = 0,
    ) -> list[EntityCandidate]:
        if not text:
            return []
        found: OrderedDict[tuple[int, int, str], EntityCandidate] = OrderedDict()

        def add(start: int, end: int, raw: str, normalized: str, hint: str) -> None:
            key = (start, end, raw)
            existing = found.get(key)
            hints = tuple(dict.fromkeys((*existing.initial_hints, hint))) if existing else (hint,)
            source = self._source(
                text, start, end, source_type, source_file, page, extractor, base_offset
            )
            found[key] = EntityCandidate(raw, normalized, source, hints)

        for pattern, hint in (
            (self.EMAIL, "email_pattern"),
            (self.MONEY, "currency_symbol"),
            (self.DECIMAL, "decimal_pattern"),
            (self.ISO_DATETIME, "iso_datetime"),
            (self.MASKED_CPF, "cpf_mask"),
            (self.FORMATTED_PHONE, "phone_format"),
            (self.BARE_NUMERIC, "numeric_sequence"),
        ):
            for match in pattern.finditer(text):
                raw = match.group(0).strip()
                add(match.start(), match.end(), raw, self._basic_normalize(raw), hint)

        for occurrence in self.ip_extractor.extract(text):
            add(
                occurrence.start,
                occurrence.end,
                occurrence.raw_text,
                occurrence.address,
                "ip_syntax",
            )

        for occurrence in self.date_extractor.extract(text):
            add(
                occurrence.start,
                occurrence.end,
                occurrence.raw_text,
                occurrence.value.isoformat(),
                "validated_date_candidate",
            )

        values = list(found.values())
        filtered = [
            candidate
            for candidate in values
            if not (
                candidate.initial_hints in {("numeric_sequence",), ("decimal_pattern",)}
                and any(
                    other is not candidate
                    and (other.source.start or 0) <= (candidate.source.start or 0)
                    and (other.source.end or 0) >= (candidate.source.end or 0)
                    and other.initial_hints not in {("numeric_sequence",), ("decimal_pattern",)}
                    for other in values
                )
            )
        ]
        return sorted(filtered, key=lambda item: (item.source.start or 0, item.source.end or 0))

    def extract_structured(
        self,
        value: object,
        *,
        source_type: EntitySourceType,
        source_file: str,
        field_path: str,
        extractor: str,
    ) -> EntityCandidate | None:
        if value is None or isinstance(value, (dict, list, tuple, set, bytes)):
            return None
        raw = str(value).strip()
        if not raw:
            return None
        hint = self._hint_from_field(field_path)
        source = EntitySource(
            source_type=source_type,
            source_file=source_file,
            context_before=field_path,
            extractor=extractor,
            field_path=field_path,
        )
        return EntityCandidate(raw, self._basic_normalize(raw), source, (hint,) if hint else ())

    def _source(
        self,
        text: str,
        start: int,
        end: int,
        source_type: EntitySourceType,
        source_file: str,
        page: int | None,
        extractor: str,
        base_offset: int,
    ) -> EntitySource:
        return EntitySource(
            source_type=source_type,
            source_file=source_file,
            page=page,
            start=base_offset + start,
            end=base_offset + end,
            context_before=text[max(0, start - self.context_radius):start],
            context_after=text[end:min(len(text), end + self.context_radius)],
            extractor=extractor,
        )

    @staticmethod
    def _basic_normalize(value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _hint_from_field(path: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", path.lower())
        for entity in (
            "cpf", "phone", "telefone", "mobile", "email", "ip", "date",
            "datetime", "money", "valor", "amount", "price", "total", "currency",
        ):
            if entity in normalized:
                return f"field_{entity}"
        return "structured_field"

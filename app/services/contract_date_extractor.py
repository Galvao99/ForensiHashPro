from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Iterable

from app.models.extracted_date import DateFormat, ExtractedDate


@dataclass(frozen=True, slots=True)
class ContractDateFinding:
    """Formato legado mantido para consumidores anteriores do serviço."""

    date: datetime
    label: str
    context: str
    score: int


class ContractDateExtractor:
    """
    Extrai datas completas de textos obtidos por PDF ou OCR.

    Formatos reconhecidos:

    - 15/07/2026
    - 15-07-2026
    - 15.07.2026
    - 15/07/26
    - 2026-07-15
    - 15 de julho de 2026
    - 15 julho 2026

    O extrator valida cada ocorrência por meio de datetime, eliminando
    datas impossíveis como 31/02/2026.
    """

    MONTHS: Final[dict[str, int]] = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    NUMERIC_DMY_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"""
        (?<![\w./-])
        (?P<day>0?[1-9]|[12]\d|3[01])
        \s*
        (?P<separator>[/.\-])
        \s*
        (?P<month>0?[1-9]|1[0-2])
        \s*
        (?P=separator)
        \s*
        (?P<year>\d{2}|\d{4})
        (?![\w/-])
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    NUMERIC_YMD_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"""
        (?<![\w./-])
        (?P<year>\d{4})
        \s*
        (?P<separator>[/.\-])
        \s*
        (?P<month>0?[1-9]|1[0-2])
        \s*
        (?P=separator)
        \s*
        (?P<day>0?[1-9]|[12]\d|3[01])
        (?![\w/-])
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    TEXTUAL_DMY_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"""
        (?<!\d)
        (?P<day>0?[1-9]|[12]\d|3[01])
        \s+
        (?:de\s+)?
        (?P<month>
            janeiro|
            fevereiro|
            março|marco|
            abril|
            maio|
            junho|
            julho|
            agosto|
            setembro|
            outubro|
            novembro|
            dezembro
        )
        \s+
        (?:de\s+)?
        (?P<year>\d{4})
        (?!\d)
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    def __init__(
        self,
        context_radius: int = 70,
        minimum_year: int = 1900,
        maximum_year: int = 2100,
    ) -> None:
        if context_radius < 0:
            raise ValueError("context_radius não pode ser negativo.")

        if minimum_year > maximum_year:
            raise ValueError(
                "minimum_year não pode ser superior a maximum_year."
            )

        self.context_radius = context_radius
        self.minimum_year = minimum_year
        self.maximum_year = maximum_year

    def extract(self, text: str | None) -> list[ExtractedDate]:
        """
        Retorna todas as datas válidas encontradas no texto.

        Datas repetidas em posições diferentes são preservadas, pois podem
        representar eventos distintos no documento.
        """

        if not text or not text.strip():
            return []

        extracted: list[ExtractedDate] = []

        extracted.extend(self._extract_numeric_dmy(text))
        extracted.extend(self._extract_numeric_ymd(text))
        extracted.extend(self._extract_textual_dmy(text))

        extracted = self._remove_overlapping_matches(extracted)

        return sorted(
            extracted,
            key=lambda item: (item.start, item.end),
        )

    def extract_values(self, text: str | None) -> list[datetime]:
        """
        Atalho para consumidores antigos que esperam somente datetime.
        """

        return [item.value for item in self.extract(text)]

    def extract_contract_dates(
        self,
        text: str | None,
    ) -> list[ContractDateFinding]:
        """Mantém a API anterior, agora apoiada na classificação robusta."""
        from app.services.contract_date_selector import ContractDateSelector

        candidates = ContractDateSelector(minimum_score=0).rank(
            self.extract(text)
        )

        return [
            ContractDateFinding(
                date=candidate.extracted_date.value,
                label="Data contratual provável",
                context=candidate.extracted_date.context,
                score=candidate.score,
            )
            for candidate in candidates
            if candidate.score > 0
        ]

    def get_best_contract_date(
        self,
        text: str | None,
    ) -> ContractDateFinding | None:
        """Mantém o retorno legado sem promover candidatas de baixa confiança."""
        findings = self.extract_contract_dates(text)
        return findings[0] if findings else None

    def extract_unique(self, text: str | None) -> list[ExtractedDate]:
        """
        Retorna somente uma ocorrência de cada data normalizada.

        Quando uma data aparece mais de uma vez, a primeira ocorrência
        identificada no documento é preservada.
        """

        unique: dict[str, ExtractedDate] = {}

        for extracted_date in self.extract(text):
            unique.setdefault(
                extracted_date.normalized,
                extracted_date,
            )

        return list(unique.values())

    def _extract_numeric_dmy(
        self,
        text: str,
    ) -> Iterable[ExtractedDate]:
        for match in self.NUMERIC_DMY_PATTERN.finditer(text):
            day = int(match.group("day"))
            month = int(match.group("month"))
            year_raw = match.group("year")

            year = self._normalize_year(year_raw)
            value = self._build_valid_date(day, month, year)

            if value is None:
                continue

            yield self._build_result(
                text=text,
                match=match,
                value=value,
                date_format=DateFormat.NUMERIC_DMY,
                has_four_digit_year=len(year_raw) == 4,
            )

    def _extract_numeric_ymd(
        self,
        text: str,
    ) -> Iterable[ExtractedDate]:
        for match in self.NUMERIC_YMD_PATTERN.finditer(text):
            day = int(match.group("day"))
            month = int(match.group("month"))
            year_raw = match.group("year")
            year = int(year_raw)

            value = self._build_valid_date(day, month, year)

            if value is None:
                continue

            yield self._build_result(
                text=text,
                match=match,
                value=value,
                date_format=DateFormat.NUMERIC_YMD,
                has_four_digit_year=True,
            )

    def _extract_textual_dmy(
        self,
        text: str,
    ) -> Iterable[ExtractedDate]:
        for match in self.TEXTUAL_DMY_PATTERN.finditer(text):
            day = int(match.group("day"))
            month_name = self._normalize_word(match.group("month"))
            year = int(match.group("year"))

            month = self.MONTHS.get(month_name)

            if month is None:
                continue

            value = self._build_valid_date(day, month, year)

            if value is None:
                continue

            raw_text = match.group(0)
            normalized_raw = self._normalize_word(raw_text)

            has_connectors = bool(
                re.search(
                    r"\bde\b",
                    normalized_raw,
                    flags=re.IGNORECASE,
                )
            )

            date_format = (
                DateFormat.TEXTUAL_DMY
                if has_connectors
                else DateFormat.TEXTUAL_DMY_WITHOUT_CONNECTORS
            )

            yield self._build_result(
                text=text,
                match=match,
                value=value,
                date_format=date_format,
                has_four_digit_year=True,
            )

    def _build_result(
        self,
        text: str,
        match: re.Match[str],
        value: datetime,
        date_format: DateFormat,
        has_four_digit_year: bool,
    ) -> ExtractedDate:
        start = match.start()
        end = match.end()

        context_start = max(0, start - self.context_radius)
        context_end = min(len(text), end + self.context_radius)

        context = text[context_start:context_end]
        context = self._clean_context(context)

        return ExtractedDate(
            value=value,
            raw_text=match.group(0).strip(),
            normalized=value.strftime("%d/%m/%Y"),
            format=date_format,
            start=start,
            end=end,
            context=context,
            has_four_digit_year=has_four_digit_year,
        )

    def _build_valid_date(
        self,
        day: int,
        month: int,
        year: int,
    ) -> datetime | None:
        if not self.minimum_year <= year <= self.maximum_year:
            return None

        try:
            return datetime(
                year=year,
                month=month,
                day=day,
            )
        except ValueError:
            return None

    @staticmethod
    def _normalize_year(year: str) -> int:
        """
        Aplica a mesma convenção normalmente utilizada pelo datetime:

        - 00 até 68: 2000 até 2068
        - 69 até 99: 1969 até 1999
        """

        if len(year) == 4:
            return int(year)

        numeric_year = int(year)

        if numeric_year <= 68:
            return 2000 + numeric_year

        return 1900 + numeric_year

    @staticmethod
    def _normalize_word(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)

        return "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        ).lower()

    @staticmethod
    def _clean_context(context: str) -> str:
        return re.sub(r"\s+", " ", context).strip()

    @staticmethod
    def _remove_overlapping_matches(
        dates: list[ExtractedDate],
    ) -> list[ExtractedDate]:
        """
        Impede que a mesma sequência seja retornada por dois padrões.

        Em uma sobreposição, preserva a ocorrência de maior extensão.
        """

        ordered = sorted(
            dates,
            key=lambda item: (
                item.start,
                -(item.end - item.start),
            ),
        )

        accepted: list[ExtractedDate] = []

        for candidate in ordered:
            overlaps = any(
                candidate.start < existing.end
                and candidate.end > existing.start
                for existing in accepted
            )

            if not overlaps:
                accepted.append(candidate)

        return accepted

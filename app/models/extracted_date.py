from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class DateFormat(str, Enum):
    NUMERIC_DMY = "numeric_dmy"
    NUMERIC_YMD = "numeric_ymd"
    TEXTUAL_DMY = "textual_dmy"
    TEXTUAL_DMY_WITHOUT_CONNECTORS = "textual_dmy_without_connectors"


@dataclass(frozen=True, slots=True)
class ExtractedDate:
    """
    Representa uma data válida identificada em um texto.

    Attributes:
        value:
            Data normalizada como datetime.

        raw_text:
            Trecho original encontrado no documento.

        normalized:
            Data padronizada no formato DD/MM/AAAA.

        format:
            Formato utilizado no texto original.

        start:
            Posição inicial da ocorrência no texto.

        end:
            Posição final da ocorrência no texto.

        context:
            Pequeno trecho ao redor da data.

        has_four_digit_year:
            Indica se o ano foi apresentado com quatro dígitos.
    """

    value: datetime
    raw_text: str
    normalized: str
    format: DateFormat
    start: int
    end: int
    context: str
    has_four_digit_year: bool = True


@dataclass(frozen=True, slots=True)
class ContractDateCandidate:
    """Candidata contextual, sem representar confirmação da pactuação."""

    extracted_date: ExtractedDate
    score: int
    reasons: tuple[str, ...]

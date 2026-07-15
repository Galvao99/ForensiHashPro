from datetime import datetime

import pytest

from app.models import DateFormat
from app.services.contract_date_extractor import ContractDateExtractor


@pytest.mark.parametrize(
    ("text", "expected_format", "four_digits"),
    [
        ("15/07/2026", DateFormat.NUMERIC_DMY, True),
        ("15-07-2026", DateFormat.NUMERIC_DMY, True),
        ("15.07.2026", DateFormat.NUMERIC_DMY, True),
        ("15/07/26", DateFormat.NUMERIC_DMY, False),
        ("2026-07-15", DateFormat.NUMERIC_YMD, True),
        ("15 de julho de 2026", DateFormat.TEXTUAL_DMY, True),
        ("15 de Julho de 2026", DateFormat.TEXTUAL_DMY, True),
        ("15 julho 2026", DateFormat.TEXTUAL_DMY_WITHOUT_CONNECTORS, True),
        ("15 de março de 2026", DateFormat.TEXTUAL_DMY, True),
        ("15 de marco de 2026", DateFormat.TEXTUAL_DMY, True),
    ],
)
def test_extracts_supported_formats(text, expected_format, four_digits):
    result = ContractDateExtractor().extract(f"Em {text}, houve assinatura.")

    assert len(result) == 1
    lowered = text.lower()
    assert result[0].value == datetime(
        2026, 7 if "jul" in lowered or "07" in text else 3, 15
    )
    assert result[0].raw_text == text
    assert result[0].normalized in {"15/07/2026", "15/03/2026"}
    assert result[0].format is expected_format
    assert result[0].has_four_digit_year is four_digits
    assert text in result[0].context
    assert result[0].start < result[0].end


def test_preserves_multiple_and_repeated_occurrences_in_source_order():
    text = "Assinado em 15/07/2026; confirmado em 20/08/2026; cópia 15/07/2026."
    dates = ContractDateExtractor().extract(text)

    assert [item.raw_text for item in dates] == [
        "15/07/2026", "20/08/2026", "15/07/2026"
    ]
    assert [item.start for item in dates] == sorted(item.start for item in dates)


def test_accepts_valid_leap_day():
    assert ContractDateExtractor().extract("29/02/2024")[0].value == datetime(2024, 2, 29)


@pytest.mark.parametrize(
    "text",
    [
        "31/02/2026", "32/01/2026", "00/01/2026", "10/13/2026",
        "29/02/2025", "12345678901234567890", "IP 10.15.07.2026",
        "hash a15/07/2026b", "versão 1.15.07.2026.4",
    ],
)
def test_rejects_invalid_or_embedded_numeric_sequences(text):
    assert ContractDateExtractor().extract(text) == []


def test_rejects_year_outside_configured_range():
    extractor = ContractDateExtractor(minimum_year=2000, maximum_year=2030)
    assert extractor.extract("15/07/1999 e 15/07/2031") == []


def test_two_digit_year_rule_is_explicit():
    dates = ContractDateExtractor().extract("01/01/68 e 01/01/69")
    assert [item.value.year for item in dates] == [2068, 1969]

from app.services.contract_date_extractor import ContractDateExtractor
from app.services.contract_date_selector import ContractDateSelector


def test_selects_contract_date_over_birth_and_due_dates():
    text = (
        "Data de nascimento: 10/05/1980.\n"
        "Data da contratação: 15/07/2026.\n"
        "Primeiro vencimento: 20/08/2026."
    )
    candidate = ContractDateSelector().select(ContractDateExtractor(35).extract(text))

    assert candidate is not None
    assert candidate.extracted_date.normalized == "15/07/2026"
    assert candidate.score > 0
    assert any("contratacao" in reason for reason in candidate.reasons)


def test_penalizes_birth_emission_and_expiration_indicators():
    text = "Nascimento: 10/05/1980. Data de emissão: 12/06/2020. Vencimento: 20/08/2026."
    ranked = ContractDateSelector().rank(ContractDateExtractor(25).extract(text))
    assert all(candidate.score < 5 for candidate in ranked)
    assert ContractDateSelector().select(ContractDateExtractor(25).extract(text)) is None


def test_prefers_pactuation_contracting_and_signature_indicators():
    for phrase in ("Data da pactuação", "Data de contratação", "Assinado em"):
        candidate = ContractDateSelector().select(
            ContractDateExtractor().extract(f"{phrase}: 15 de julho de 2026")
        )
        assert candidate is not None
        assert candidate.extracted_date.normalized == "15/07/2026"


def test_tie_is_resolved_by_first_source_position():
    dates = ContractDateExtractor().extract(
        "Assinado em 15/07/2026. Assinado em 16/07/2026."
    )
    candidate = ContractDateSelector().select(dates)
    assert candidate is not None
    assert candidate.extracted_date.normalized == "15/07/2026"


def test_no_dates_or_contextual_indicators_returns_none():
    selector = ContractDateSelector()
    assert selector.select([]) is None
    assert selector.select(ContractDateExtractor().extract("Referência: 15/07/2026.")) is None

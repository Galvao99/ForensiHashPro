from __future__ import annotations

import pytest
from pathlib import Path
from types import SimpleNamespace

from app.entities import (
    CandidateExtractor,
    CpfValidator,
    DatetimeValidator,
    EmailValidator,
    EntityCandidate,
    EntityResolver,
    EntityExtractionService,
    EntitySource,
    EntitySourceType,
    EntityType,
    IpValidator,
    MoneyValidator,
    PhoneValidator,
)
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.ocr_context_rules import OcrContextRule
from app.services.text_extraction_service import TextExtractionResult, TextSegment


def candidate(
    value: str,
    *,
    before: str = "",
    after: str = "",
    source_type: EntitySourceType = EntitySourceType.NATIVE_TEXT,
    hints: tuple[str, ...] = (),
) -> EntityCandidate:
    return EntityCandidate(
        value,
        value,
        EntitySource(
            source_type=source_type,
            source_file="caso-anonimizado.pdf",
            start=10,
            end=10 + len(value),
            context_before=before,
            context_after=after,
            extractor="test",
        ),
        hints,
    )


@pytest.mark.parametrize("value", ["12345678909", "123.456.789-09"])
def test_valid_cpf_and_mask(value: str) -> None:
    result = CpfValidator().validate(candidate(value))
    assert result.valid is True
    assert result.normalized_value == "12345678909"


def test_invalid_cpf_checksum() -> None:
    assert CpfValidator().validate(candidate("12345678901")).valid is False


@pytest.mark.parametrize(
    ("value", "normalized", "kind"),
    [
        ("(21) 98696-7225", "+5521986967225", "mobile"),
        ("+55 21 98696-7225", "+5521986967225", "mobile"),
        ("(21) 3269-6722", "+552132696722", "landline"),
    ],
)
def test_brazilian_phone_formats(value: str, normalized: str, kind: str) -> None:
    result = PhoneValidator().validate(candidate(value))
    assert result.valid is True
    assert result.normalized_value == normalized
    assert result.attributes["kind"] == kind


def test_cpf_that_is_not_a_valid_phone_resolves_as_cpf() -> None:
    entity = EntityResolver().resolve([candidate("12345678909")]).entities[0]
    assert entity.entity_type is EntityType.CPF


def test_number_valid_as_cpf_and_phone_uses_context() -> None:
    resolver = EntityResolver()
    phone = resolver.resolve([candidate("11900000083", before="Telefone para contato: ")]).entities[0]
    cpf = resolver.resolve([candidate("11900000083", before="CPF do titular: ")]).entities[0]
    assert phone.entity_type is EntityType.PHONE
    assert cpf.entity_type is EntityType.CPF


def test_real_ambiguity_is_preserved() -> None:
    entity = EntityResolver().resolve([candidate("11900000083")]).entities[0]
    assert entity.entity_type is EntityType.AMBIGUOUS
    assert {item.entity_type for item in entity.hypotheses} == {EntityType.CPF, EntityType.PHONE}


@pytest.mark.parametrize("value", ["11900000083", "98765432101"])
def test_contract_or_random_number_is_not_forced_to_document(value: str) -> None:
    entity = EntityResolver().resolve([candidate(value, before="Número do contrato: ")]).entities[0]
    assert entity.entity_type is EntityType.UNKNOWN_NUMERIC_IDENTIFIER


@pytest.mark.parametrize(
    ("value", "valid", "normalized"),
    [
        ("192.168.1.10", True, "192.168.1.10"),
        ("999.168.1.10", False, None),
        ("2001:0db8::1", True, "2001:db8::1"),
    ],
)
def test_ip_validation(value: str, valid: bool, normalized: str | None) -> None:
    result = IpValidator().validate(candidate(value))
    assert result.valid is valid
    assert result.normalized_value == normalized


def test_money_with_symbol() -> None:
    result = MoneyValidator().validate(candidate("R$ 1.234,56", hints=("currency_symbol",)))
    assert result.valid is True
    assert result.normalized_value == "1234.56"
    assert result.attributes["currency"] == "BRL"


def test_money_with_context_and_decimal_without_context() -> None:
    assert MoneyValidator().validate(candidate("1234,56", before="Valor da parcela: ")).valid is True
    assert MoneyValidator().validate(candidate("1234,56", before="Medição técnica: ")).valid is False


@pytest.mark.parametrize(
    ("value", "timezone_present", "precision"),
    [
        ("15/07/2026", False, "date"),
        ("2026-07-15T10:30:45-03:00", True, "second"),
        ("2026-07-15T10:30:00", False, "second"),
    ],
)
def test_datetime_validation(value: str, timezone_present: bool, precision: str) -> None:
    result = DatetimeValidator().validate(candidate(value))
    assert result.valid is True
    assert result.attributes == {"precision": precision, "timezone_present": timezone_present}


def test_email_valid_and_invalid() -> None:
    assert EmailValidator().validate(candidate("perito@example.org")).valid is True
    assert EmailValidator().validate(candidate("a..b@example.org")).valid is False


def test_native_and_ocr_provenance_and_deduplication() -> None:
    extractor = CandidateExtractor()
    native = extractor.extract_text(
        "Telefone: (21) 98696-7225",
        source_type=EntitySourceType.NATIVE_TEXT,
        source_file="evidence.pdf",
        page=1,
    )
    ocr = extractor.extract_text(
        "Contato: +55 21 98696-7225",
        source_type=EntitySourceType.OCR,
        source_file="evidence.pdf",
        page=2,
    )
    entities = EntityResolver().resolve([*native, *ocr]).entities
    phone = next(item for item in entities if item.entity_type is EntityType.PHONE)
    assert phone.normalized_value == "+5521986967225"
    assert {source.source_type for source in phone.sources} == {
        EntitySourceType.NATIVE_TEXT,
        EntitySourceType.OCR,
    }
    assert {source.page for source in phone.sources} == {1, 2}


def test_context_labels_resolve_cpf_phone_and_money() -> None:
    extractor = CandidateExtractor()
    text = "CPF: 12345678909 Telefone: 21986967225 Valor da parcela: 1234,56"
    entities = EntityResolver().resolve(
        extractor.extract_text(
            text,
            source_type=EntitySourceType.NATIVE_TEXT,
            source_file="contrato-anonimizado.pdf",
        )
    ).entities
    assert {entity.entity_type for entity in entities} >= {
        EntityType.CPF,
        EntityType.PHONE,
        EntityType.MONEY,
    }


def test_nearby_numeric_sequences_remain_separate() -> None:
    extractor = CandidateExtractor(context_radius=20)
    entities = EntityResolver().resolve(
        extractor.extract_text(
            "Contrato 84726193014; referência 77382910; telefone 21986967225.",
            source_type=EntitySourceType.OCR,
            source_file="proposta-anonimizada.png",
            page=1,
        )
    ).entities
    normalized = {entity.normalized_value for entity in entities}
    assert "84726193014" in normalized
    assert "77382910" in normalized
    assert "+5521986967225" in normalized


def test_nearest_label_resolves_adjacent_dual_hypothesis_numbers() -> None:
    text = "CPF: 11900000083; Telefone: 11900000083"
    entities = EntityResolver().resolve(
        CandidateExtractor(context_radius=30).extract_text(
            text,
            source_type=EntitySourceType.NATIVE_TEXT,
            source_file="cadastro-anonimizado.pdf",
        )
    ).entities
    assert {entity.entity_type for entity in entities} == {
        EntityType.CPF,
        EntityType.PHONE,
    }


def test_confidence_is_deterministic_and_explained() -> None:
    item = candidate("123.456.789-09", before="CPF: ")
    first = EntityResolver().resolve([item]).entities[0]
    second = EntityResolver().resolve([item]).entities[0]
    assert first.confidence == second.confidence
    assert first.confidence_components
    assert {component.component for component in first.confidence_components} >= {
        "structural_validation", "context", "formatting"
    }


def test_structured_json_field_has_field_provenance() -> None:
    extracted = CandidateExtractor().extract_structured(
        "perito@example.org",
        source_type=EntitySourceType.JSON,
        source_file="dados-anonimizados.json",
        field_path="$.cliente.email",
        extractor="rust_json_field",
    )
    assert extracted is not None
    entity = EntityResolver().resolve([extracted]).entities[0]
    assert entity.entity_type is EntityType.EMAIL
    assert entity.sources[0].field_path == "$.cliente.email"
    assert entity.sources[0].source_type is EntitySourceType.JSON


def test_legacy_correlation_rule_consumes_resolved_entities() -> None:
    source = EntitySource(
        source_type=EntitySourceType.OCR,
        source_file="evidence-key",
        page=2,
        extractor="entity_resolver_v2",
    )
    context = InvestigationContext(
        extracted_texts={"evidence-key": "Telefone: 21986967225"},
        resolved_entities={
            "evidence-key": [
                EntityResolver().resolve(
                    [
                        EntityCandidate(
                            "21986967225",
                            "21986967225",
                            source,
                            ("field_telefone",),
                        )
                    ]
                ).entities[0]
            ]
        },
    )

    findings = OcrContextRule().evaluate(context)

    phone = next(item for item in findings if item.title == "Telefone localizado no conteúdo")
    assert phone.metadata["telefones"] == ["+5521986967225"]
    assert all(item.title != "CPF com estrutura inválida" for item in findings)


def test_analysis_source_segments_flow_through_entity_service(tmp_path: Path) -> None:
    result = SimpleNamespace(
        file_info=SimpleNamespace(path=tmp_path / "evidence.pdf"),
        extracted_text="",
        metadata=SimpleNamespace(raw={}),
        json_analysis=None,
    )
    text_result = TextExtractionResult(
        text="CPF: 12345678909\nTelefone: 21986967225",
        source="ocr",
        segments=[
            TextSegment("CPF: 12345678909", "native_text", 1),
            TextSegment("Telefone: 21986967225", "ocr", 2),
        ],
    )

    entities = EntityExtractionService().resolve_analysis(
        result, text_result=text_result
    ).entities

    assert {entity.entity_type for entity in entities} == {
        EntityType.CPF,
        EntityType.PHONE,
    }
    assert {entity.sources[0].source_type for entity in entities} == {
        EntitySourceType.NATIVE_TEXT,
        EntitySourceType.OCR,
    }

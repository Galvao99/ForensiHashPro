from __future__ import annotations

import ipaddress
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.entities.models import EntityCandidate, EntityType, ValidationResult


class EntityValidator(Protocol):
    entity_type: EntityType

    def validate(self, candidate: EntityCandidate) -> ValidationResult: ...


def _digits(value: str) -> str:
    return "".join(character for character in value if character.isdigit())


class CpfValidator:
    entity_type = EntityType.CPF

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        digits = _digits(candidate.raw_value)
        if len(digits) != 11:
            return ValidationResult(self.entity_type, False, reasons=("CPF exige 11 dígitos.",))
        if digits == digits[0] * 11:
            return ValidationResult(self.entity_type, False, reasons=("Sequência repetida não é CPF válido.",))
        first = (sum(int(digits[index]) * (10 - index) for index in range(9)) * 10) % 11
        first = 0 if first == 10 else first
        second = (sum(int(digits[index]) * (11 - index) for index in range(10)) * 10) % 11
        second = 0 if second == 10 else second
        if first != int(digits[9]) or second != int(digits[10]):
            return ValidationResult(self.entity_type, False, reasons=("Checksum de CPF inválido.",))
        masked = bool(re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", candidate.raw_value.strip()))
        return ValidationResult(
            self.entity_type,
            True,
            digits,
            structural_confidence=0.65,
            formatting_confidence=0.10 if masked else 0.0,
            attributes={"checksum_valid": True, "masked": masked},
            reasons=("Checksum oficial de CPF válido.",),
        )


class PhoneValidator:
    entity_type = EntityType.PHONE
    VALID_DDDS = frozenset(
        {11, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 24, 27, 28,
         31, 32, 33, 34, 35, 37, 38, 41, 42, 43, 44, 45, 46, 47, 48,
         49, 51, 53, 54, 55, 61, 62, 63, 64, 65, 66, 67, 68, 69, 71,
         73, 74, 75, 77, 79, 81, 82, 83, 84, 85, 86, 87, 88, 89, 91,
         92, 93, 94, 95, 96, 97, 98, 99}
    )

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        raw = candidate.raw_value.strip()
        digits = _digits(raw)
        has_country = digits.startswith("55") and len(digits) in {12, 13}
        national = digits[2:] if has_country else digits
        if len(national) not in {10, 11}:
            return ValidationResult(self.entity_type, False, reasons=("Telefone BR exige DDD e 8 ou 9 dígitos locais.",))
        ddd = int(national[:2])
        if ddd not in self.VALID_DDDS:
            return ValidationResult(self.entity_type, False, reasons=("DDD brasileiro inválido.",))
        local = national[2:]
        kind = "mobile" if len(local) == 9 and local.startswith("9") else "landline" if len(local) == 8 and local[0] in "2345" else None
        if kind is None:
            return ValidationResult(self.entity_type, False, reasons=("Prefixo local incompatível com telefone fixo ou celular BR.",))
        formatted = bool(re.search(r"[()+.\s-]", raw))
        return ValidationResult(
            self.entity_type,
            True,
            f"+55{national}",
            structural_confidence=0.55,
            formatting_confidence=0.10 if formatted or has_country else 0.0,
            attributes={"country": "BR", "ddd": ddd, "kind": kind},
            reasons=(f"Formato brasileiro válido ({kind}).",),
        )


class IpValidator:
    entity_type = EntityType.IP

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        try:
            address = ipaddress.ip_address(candidate.raw_value.strip())
        except ValueError:
            return ValidationResult(self.entity_type, False, reasons=("Endereço IP sintaticamente inválido.",))
        normalized = address.compressed.lower() if address.version == 6 else str(address)
        return ValidationResult(
            self.entity_type, True, normalized, structural_confidence=0.80,
            attributes={"version": address.version},
            reasons=(f"IPv{address.version} validado pela biblioteca padrão.",),
        )


class MoneyValidator:
    entity_type = EntityType.MONEY
    MONEY_TERMS = ("valor", "parcela", "preço", "preco", "total", "pagamento", "saldo", "r$")

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        raw = candidate.raw_value.strip()
        context = candidate.source.context.lower()
        has_symbol = raw.lower().startswith("r$") or "currency" in candidate.initial_hints
        has_context = any(term in context for term in self.MONEY_TERMS)
        if not has_symbol and not has_context:
            return ValidationResult(self.entity_type, False, reasons=("Número decimal sem indicador monetário.",))
        numeric = re.sub(r"^r\$\s*", "", raw, flags=re.IGNORECASE).strip()
        if not re.fullmatch(r"(?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})", numeric):
            return ValidationResult(self.entity_type, False, reasons=("Formato monetário brasileiro inválido.",))
        try:
            value = Decimal(numeric.replace(".", "").replace(",", "."))
        except InvalidOperation:
            return ValidationResult(self.entity_type, False, reasons=("Valor monetário não pôde ser normalizado.",))
        return ValidationResult(
            self.entity_type, True, format(value, ".2f"),
            structural_confidence=0.50,
            formatting_confidence=0.20 if has_symbol else 0.0,
            attributes={"currency": "BRL", "decimal": format(value, ".2f")},
            reasons=(("Símbolo R$ presente." if has_symbol else "Contexto monetário presente."),),
        )


class DatetimeValidator:
    entity_type = EntityType.DATETIME
    FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        raw = candidate.raw_value.strip()
        parsed: datetime | None = None
        for date_format in self.FORMATS:
            try:
                parsed = datetime.strptime(raw, date_format)
                break
            except ValueError:
                continue
        if parsed is None:
            if "validated_date_candidate" in candidate.initial_hints:
                try:
                    parsed = datetime.fromisoformat(candidate.normalized_candidate)
                except ValueError:
                    parsed = None
        if parsed is None:
            iso = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
            try:
                parsed = datetime.fromisoformat(iso)
            except ValueError:
                return ValidationResult(self.entity_type, False, reasons=("Data/hora inválida.",))
        has_time = "T" in raw or bool(re.search(r"\d\s+\d{2}:\d{2}", raw))
        precision = "second" if re.search(r":\d{2}(?:[.,]\d+)?", raw) else "minute" if has_time else "date"
        normalized = parsed.isoformat()
        return ValidationResult(
            self.entity_type, True, normalized, structural_confidence=0.70,
            attributes={"precision": precision, "timezone_present": parsed.tzinfo is not None},
            reasons=("Data/hora validada semanticamente.",),
        )


class EmailValidator:
    entity_type = EntityType.EMAIL
    PATTERN = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")

    def validate(self, candidate: EntityCandidate) -> ValidationResult:
        value = candidate.raw_value.strip()
        if len(value) > 254 or not self.PATTERN.fullmatch(value):
            return ValidationResult(self.entity_type, False, reasons=("Sintaxe de e-mail inválida.",))
        local, domain = value.rsplit("@", 1)
        labels = domain.split(".")
        if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
            return ValidationResult(self.entity_type, False, reasons=("Parte local de e-mail inválida.",))
        if any(len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
            return ValidationResult(self.entity_type, False, reasons=("Domínio de e-mail inválido.",))
        return ValidationResult(
            self.entity_type, True, f"{local}@{domain.lower()}", structural_confidence=0.70,
            attributes={"domain": domain.lower()}, reasons=("Sintaxe conservadora de e-mail válida.",),
        )


DEFAULT_VALIDATORS: tuple[EntityValidator, ...] = (
    CpfValidator(), PhoneValidator(), IpValidator(), MoneyValidator(),
    DatetimeValidator(), EmailValidator(),
)

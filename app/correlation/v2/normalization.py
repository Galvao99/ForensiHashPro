from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import ipaddress
import re
from urllib.parse import urlsplit, urlunsplit

from app.correlation.v2.models import EntityType


@dataclass(frozen=True, slots=True)
class NormalizedValue:
    value: str
    display_value: str


class CorrelationNormalizer:
    _EMAIL = re.compile(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
    _HEX = re.compile(r"[0-9a-fA-F]+")

    def normalize(self, entity_type: EntityType, raw_value: object) -> NormalizedValue | None:
        raw = str(raw_value).strip()
        if not raw:
            return None
        method = getattr(self, f"_normalize_{entity_type.value}")
        value = method(raw)
        return NormalizedValue(value, raw) if value is not None else None

    def _normalize_sha256(self, raw: str) -> str | None:
        return raw.lower() if len(raw) == 64 and self._HEX.fullmatch(raw) else None

    def _normalize_md5(self, raw: str) -> str | None:
        return raw.lower() if len(raw) == 32 and self._HEX.fullmatch(raw) else None

    @staticmethod
    def _normalize_ip(raw: str) -> str | None:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError:
            return None
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return address.compressed.lower() if address.version == 6 else str(address)

    def _normalize_email(self, raw: str) -> str | None:
        if len(raw) > 254 or not self._EMAIL.fullmatch(raw):
            return None
        local, domain = raw.rsplit("@", 1)
        if len(local) > 64 or local.startswith(".") or local.endswith(".") or ".." in local:
            return None
        labels = domain.split(".")
        if any(not label or len(label) > 63 or label.startswith("-") or label.endswith("-") for label in labels):
            return None
        return f"{local}@{domain.lower()}"

    @staticmethod
    def _normalize_phone(raw: str) -> str | None:
        if not re.fullmatch(r"\+?[\d().\s-]+", raw):
            return None
        digits = "".join(character for character in raw if character.isdigit())
        if not 7 <= len(digits) <= 15:
            return None
        return f"+{digits}" if raw.lstrip().startswith("+") else digits

    @staticmethod
    def _cpf_checksum(digits: str) -> bool:
        if len(digits) != 11 or digits == digits[0] * 11:
            return False
        first = (sum(int(digits[index]) * (10 - index) for index in range(9)) * 10) % 11
        second = (sum(int(digits[index]) * (11 - index) for index in range(10)) * 10) % 11
        return (0 if first == 10 else first) == int(digits[9]) and (0 if second == 10 else second) == int(digits[10])

    def _normalize_cpf(self, raw: str) -> str | None:
        digits = re.sub(r"\D", "", raw)
        return digits if self._cpf_checksum(digits) else None

    @staticmethod
    def _normalize_cnpj(raw: str) -> str | None:
        digits = re.sub(r"\D", "", raw)
        if len(digits) != 14 or digits == digits[0] * 14:
            return None
        def digit(base: str, weights: tuple[int, ...]) -> str:
            remainder = sum(int(value) * weight for value, weight in zip(base, weights)) % 11
            return str(0 if remainder < 2 else 11 - remainder)
        first = digit(digits[:12], (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        second = digit(digits[:12] + first, (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2))
        return digits if digits[-2:] == first + second else None

    @staticmethod
    def _normalize_url(raw: str) -> str | None:
        try:
            parsed = urlsplit(raw)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                return None
            hostname = parsed.hostname.lower()
            host = f"[{hostname}]" if ":" in hostname else hostname
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            if parsed.username is not None:
                credentials = parsed.username
                if parsed.password is not None:
                    credentials += f":{parsed.password}"
                host = f"{credentials}@{host}"
            return urlunsplit((parsed.scheme.lower(), host, parsed.path, parsed.query, parsed.fragment))
        except ValueError:
            return None

    @staticmethod
    def _normalize_timestamp(raw: str) -> str | None:
        candidate = raw[:-1] + "+00:00" if raw.endswith(("Z", "z")) else raw
        try:
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
                return date.fromisoformat(candidate).isoformat()
            return datetime.fromisoformat(candidate).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _normalize_filename(raw: str) -> str | None:
        value = raw.replace("\\", "/").rsplit("/", 1)[-1].strip()
        return value.casefold() if value and value not in {".", ".."} else None

    @staticmethod
    def _normalize_document_identifier(raw: str) -> str | None:
        value = raw.strip()
        return value if value else None

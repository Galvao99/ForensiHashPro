import ipaddress
import re


class IpParser:
    """
    Extrai e normaliza endereços IPv4 e IPv6 encontrados em textos,
    logs, OCR ou trilhas de contratação.
    """

    IPV4_REGEX = re.compile(
        r"\b(?:\d{1,3}\.){3}\d{1,3}\b"
    )

    IPV6_REGEX = re.compile(
        r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"
    )

    @classmethod
    def extract_all(cls, text: str | None) -> list[str]:
        if not text:
            return []

        candidates = []

        candidates.extend(cls.IPV4_REGEX.findall(text))
        candidates.extend(cls.IPV6_REGEX.findall(text))

        valid_ips: list[str] = []

        for candidate in candidates:
            normalized = cls.normalize(candidate)

            if normalized and normalized not in valid_ips:
                valid_ips.append(normalized)

        return valid_ips

    @classmethod
    def normalize(cls, value: str | None) -> str | None:
        if not value:
            return None

        cleaned = (
            value.strip()
            .replace("[", "")
            .replace("]", "")
            .replace("(", "")
            .replace(")", "")
            .replace(",", "")
            .replace(";", "")
        )

        try:
            parsed = ipaddress.ip_address(cleaned)
            return str(parsed)
        except ValueError:
            return None

    @classmethod
    def is_public(cls, value: str | None) -> bool:
        normalized = cls.normalize(value)

        if not normalized:
            return False

        return ipaddress.ip_address(normalized).is_global
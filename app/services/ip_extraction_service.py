from __future__ import annotations

import ipaddress
import re
from collections.abc import Iterable
from typing import Final

from app.models.detected_ip import (
    DetectedIp,
    IpClassification,
)


class IpExtractionService:
    IPV4_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"""
        (?<![\d.])
        (?P<address>
            \d{1,3}
            (?:\.\d{1,3}){3}
        )
        (?!\d|\.\d)
        """,
        re.VERBOSE,
    )

    IPV6_PATTERN: Final[re.Pattern[str]] = re.compile(
        r"""
        (?<![0-9A-Fa-f:])
        (?P<address>
            (?:
                ::(?:ffff(?::0{1,4})?:)?
                (?:
                    25[0-5]
                    |2[0-4]\d
                    |1?\d?\d
                )
                (?:
                    \.
                    (?:
                        25[0-5]
                        |2[0-4]\d
                        |1?\d?\d
                    )
                ){3}
                |
                (?:[0-9A-Fa-f]{1,4}:){7}
                [0-9A-Fa-f]{1,4}
                |
                (?:[0-9A-Fa-f]{1,4}:){1,7}:
                |
                (?:[0-9A-Fa-f]{1,4}:){1,6}
                :[0-9A-Fa-f]{1,4}
                |
                (?:[0-9A-Fa-f]{1,4}:){1,5}
                (?::[0-9A-Fa-f]{1,4}){1,2}
                |
                (?:[0-9A-Fa-f]{1,4}:){1,4}
                (?::[0-9A-Fa-f]{1,4}){1,3}
                |
                (?:[0-9A-Fa-f]{1,4}:){1,3}
                (?::[0-9A-Fa-f]{1,4}){1,4}
                |
                (?:[0-9A-Fa-f]{1,4}:){1,2}
                (?::[0-9A-Fa-f]{1,4}){1,5}
                |
                [0-9A-Fa-f]{1,4}:
                (?:(?::[0-9A-Fa-f]{1,4}){1,6})
                |
                :
                (?:(?::[0-9A-Fa-f]{1,4}){1,7}|:)
                |
                fe80:
                (?::[0-9A-Fa-f]{0,4}){0,4}
                %[0-9A-Za-z_.-]+
            )
        )
        (?![0-9A-Fa-f:])
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    CGNAT_NETWORK: Final[ipaddress.IPv4Network] = (
        ipaddress.ip_network("100.64.0.0/10")
    )

    def __init__(
        self,
        *,
        context_radius: int = 80,
    ) -> None:
        ...

    def __init__(
        self,
        *,
        context_radius: int = 80,
    ) -> None:
        if context_radius < 0:
            raise ValueError(
                "context_radius não pode ser negativo."
            )

        self.context_radius = context_radius

    def extract(
        self,
        text: str | None,
    ) -> list[DetectedIp]:
        """
        Extrai todas as ocorrências válidas de IPv4 e IPv6.

        O mesmo endereço pode aparecer mais de uma vez, desde que em
        posições distintas. Isso permite contabilizar ocorrências e
        preservar os respectivos contextos.
        """

        if not text or not text.strip():
            return []

        candidates: list[DetectedIp] = []

        candidates.extend(
            self._extract_from_pattern(
                text=text,
                pattern=self.IPV4_PATTERN,
                expected_version=4,
            )
        )

        candidates.extend(
            self._extract_from_pattern(
                text=text,
                pattern=self.IPV6_PATTERN,
                expected_version=6,
            )
        )

        candidates = self._remove_overlapping_occurrences(
            candidates
        )

        return sorted(
            candidates,
            key=lambda item: (
                item.start,
                item.end,
            ),
        )

    def extract_unique(
        self,
        text: str | None,
    ) -> list[DetectedIp]:
        """
        Retorna apenas a primeira ocorrência de cada IP normalizado.
        """

        unique: dict[str, DetectedIp] = {}

        for detected_ip in self.extract(text):
            unique.setdefault(
                detected_ip.address,
                detected_ip,
            )

        return list(unique.values())

    def extract_addresses(
        self,
        text: str | None,
    ) -> list[str]:
        """
        API simplificada para consumidores que esperam `list[str]`.
        """

        return [
            detected_ip.address
            for detected_ip in self.extract_unique(text)
        ]

    def group_occurrences(
        self,
        detected_ips: Iterable[DetectedIp],
    ) -> dict[str, list[DetectedIp]]:
        """
        Agrupa ocorrências pelo endereço normalizado.
        """

        grouped: dict[str, list[DetectedIp]] = {}

        for detected_ip in detected_ips:
            grouped.setdefault(
                detected_ip.address,
                [],
            ).append(detected_ip)

        return grouped

    def _extract_from_pattern(
        self,
        *,
        text: str,
        pattern: re.Pattern[str],
        expected_version: int,
    ) -> Iterable[DetectedIp]:
        for match in pattern.finditer(text):
            raw_text = match.group("address")

            parsed_address = self._parse_candidate(
                raw_text
            )

            if parsed_address is None:
                continue

            if parsed_address.version != expected_version:
                continue

            start = match.start("address")
            end = match.end("address")

            yield DetectedIp(
                address=self._normalize_address(
                    parsed_address
                ),
                raw_text=raw_text,
                version=parsed_address.version,
                classification=self._classify_address(
                    parsed_address
                ),
                start=start,
                end=end,
                context=self._build_context(
                    text=text,
                    start=start,
                    end=end,
                ),
            )

    @staticmethod
    def _parse_candidate(
        value: str,
    ) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
        candidate = value.strip()

        # IPv6 pode vir acompanhado de zone identifier:
        # fe80::1%eth0
        #
        # O objeto IPv6Address aceita zone identifiers em versões atuais
        # do Python, mas removemos apenas para normalização e classificação
        # previsíveis entre ambientes.
        address_without_scope = candidate.split(
            "%",
            maxsplit=1,
        )[0]

        try:
            return ipaddress.ip_address(
                address_without_scope
            )
        except ValueError:
            return None

    @staticmethod
    def _normalize_address(
        address: ipaddress.IPv4Address
        | ipaddress.IPv6Address,
    ) -> str:
        if isinstance(
            address,
            ipaddress.IPv6Address,
        ):
            return address.compressed.lower()

        return str(address)

    def _classify_address(
        self,
        address: ipaddress.IPv4Address
        | ipaddress.IPv6Address,
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
            isinstance(address, ipaddress.IPv4Address)
            and address in self.CGNAT_NETWORK
        ):
            return IpClassification.CGNAT

        if address.is_private:
            return IpClassification.PRIVATE

        if address.is_reserved:
            return IpClassification.RESERVED

        return IpClassification.PUBLIC

    def _build_context(
        self,
        *,
        text: str,
        start: int,
        end: int,
    ) -> str:
        context_start = max(
            0,
            start - self.context_radius,
        )
        context_end = min(
            len(text),
            end + self.context_radius,
        )

        context = text[
            context_start:context_end
        ]

        return self._clean_context(context)

    @staticmethod
    def _clean_context(
        context: str,
    ) -> str:
        return re.sub(
            r"\s+",
            " ",
            context,
        ).strip()

    @staticmethod
    def _remove_overlapping_occurrences(
        detected_ips: list[DetectedIp],
    ) -> list[DetectedIp]:
        """
        Evita duplicidade quando uma região do texto for capturada
        simultaneamente por padrões diferentes.

        Em caso de sobreposição, preserva a ocorrência de maior extensão.
        """

        ordered = sorted(
            detected_ips,
            key=lambda item: (
                item.start,
                -(item.end - item.start),
            ),
        )

        accepted: list[DetectedIp] = []

        for candidate in ordered:
            overlaps = any(
                candidate.start < existing.end
                and candidate.end > existing.start
                for existing in accepted
            )

            if not overlaps:
                accepted.append(candidate)

        return accepted
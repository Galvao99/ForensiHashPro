from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class IpClassification(str, Enum):
    PUBLIC = "public"
    PRIVATE = "private"
    CGNAT = "cgnat"
    LOOPBACK = "loopback"
    LINK_LOCAL = "link_local"
    MULTICAST = "multicast"
    RESERVED = "reserved"
    UNSPECIFIED = "unspecified"


@dataclass(frozen=True, slots=True)
class DetectedIp:
    """
    Representa uma ocorrência válida de endereço IP identificada
    em texto livre, PDF ou conteúdo extraído por OCR.

    `address` contém o endereço normalizado.

    `raw_text` preserva exatamente o trecho encontrado no documento.
    Isso é especialmente relevante para IPv6, cuja representação pode
    ser comprimida ou expandida de formas diferentes.
    """

    address: str
    raw_text: str
    version: int
    classification: IpClassification
    start: int
    end: int
    context: str

    @property
    def is_ipv4(self) -> bool:
        return self.version == 4

    @property
    def is_ipv6(self) -> bool:
        return self.version == 6
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class IpLookupResult:
    """
    Resultado consolidado de uma consulta de contexto de IP.

    Campos indisponíveis no plano ou no retorno da API permanecem
    como None, sem interromper o fluxo da análise.
    """

    ip: str
    provider: str = ""

    # Classificação local
    ip_version: str = ""
    network_type: str = ""
    is_public: bool = False

    # Geolocalização
    country_code: str | None = None
    country: str | None = None
    region: str | None = None
    district: str | None = None
    city: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    zip_code: str | None = None
    time_zone: str | None = None

    # Rede
    isp: str | None = None
    organization: str | None = None
    domain: str | None = None
    asn: str | None = None
    as_name: str | None = None
    usage_type: str | None = None
    address_type: str | None = None
    net_speed: str | None = None

    # Telefonia e rede móvel
    idd_code: str | None = None
    area_code: str | None = None
    mobile_country_code: str | None = None
    mobile_network_code: str | None = None
    mobile_brand: str | None = None

    # Proxy e reputação
    is_proxy: bool | None = None
    proxy_type: str | None = None
    proxy_provider: str | None = None
    proxy_last_seen: int | None = None
    proxy_threat: str | None = None
    fraud_score: int | None = None

    # Indicadores derivados
    is_vpn: bool | None = None
    is_tor: bool | None = None
    is_datacenter: bool | None = None
    is_residential_proxy: bool | None = None

    # Controle da consulta
    lookup_timestamp: datetime | None = None
    lookup_performed: bool = True
    severity: str = "ok"
    message: str = ""

    # Retorno integral para auditoria
    raw: dict[str, Any] | None = None

    @property
    def location_summary(self) -> str:
        if not self.lookup_performed:
            return "Não aplicável"

        parts = [
            self.city,
            self.district,
            self.region,
            self.country,
        ]

        return (
            ", ".join(part for part in parts if part)
            or "Localização não identificada"
        )

    @property
    def network_summary(self) -> str:
        parts = [
            self.isp,
            self.organization,
            self.asn,
        ]

        return (
            " • ".join(
                part for part in parts if part
            )
            or "Rede não identificada"
        )

    @property
    def risk_summary(self) -> str:
        indicators: list[str] = []

        if self.is_datacenter:
            indicators.append("Data Center")

        if self.is_vpn:
            indicators.append("VPN")

        if self.is_tor:
            indicators.append("Tor")

        if self.is_residential_proxy:
            indicators.append("Proxy residencial")

        if self.is_proxy and not indicators:
            indicators.append("Proxy")

        if self.fraud_score is not None:
            indicators.append(
                f"Score de fraude: {self.fraud_score}"
            )

        return (
            " • ".join(indicators)
            or "Sem indicadores adicionais"
        )

    @property
    def technical_summary(self) -> str:
        version = self.ip_version or "versão não identificada"
        network_type = (
            self.network_type
            or "tipo não identificado"
        )

        base = (
            f"{self.ip} "
            f"({version} / {network_type})"
        )

        if self.lookup_performed:
            return f"{base} — {self.location_summary}"

        return (
            f"{base} — consulta externa não realizada"
        )
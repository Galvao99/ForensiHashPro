from abc import ABC, abstractmethod
from datetime import datetime

import requests

from app.integrations.ip.ip_exceptions import (
    InvalidIpLookupError,
    IpRateLimitError,
    MissingIpApiKeyError,
)
from app.integrations.ip.ip_models import IpLookupResult


class BaseIpClient(ABC):
    @abstractmethod
    def lookup(self, ip: str) -> IpLookupResult:
        raise NotImplementedError


class Ip2LocationClient(BaseIpClient):
    BASE_URL = "https://api.ip2location.io/"

    def __init__(self, api_key: str, timeout: int = 15) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout

    def lookup(self, ip: str) -> IpLookupResult:
        if not self.api_key:
            raise MissingIpApiKeyError("API Key da IP2Location não configurada.")

        response = requests.get(
            self.BASE_URL,
            params={
                "key": self.api_key,
                "ip": ip,
                "format": "json",
            },
            timeout=self.timeout,
        )

        data = response.json()

        if response.status_code == 429 or "limit" in str(data).lower():
            raise IpRateLimitError("Limite de consultas da API atingido.")

        if response.status_code != 200:
            raise InvalidIpLookupError(
                f"Falha na consulta de IP. Status HTTP: {response.status_code}"
            )

        if data.get("error"):
            raise InvalidIpLookupError(str(data.get("error")))

        return IpLookupResult(
            ip=data.get("ip", ip),
            provider="IP2Location.io",
            ip_version="IPv6" if ":" in data.get("ip", ip) else "IPv4",
            network_type="Public",
            is_public=True,
            country=data.get("country_name"),
            region=data.get("region_name"),
            city=data.get("city_name"),
            latitude=self._to_float(data.get("latitude")),
            longitude=self._to_float(data.get("longitude")),
            isp=data.get("isp"),
            organization=data.get("organization"),
            asn=data.get("asn"),
            is_proxy=self._to_bool(data.get("is_proxy")),
            lookup_timestamp=datetime.now(),
            raw=data,
        )

    def _to_float(self, value: object) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_bool(self, value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in {"true", "yes", "1"}
        return None
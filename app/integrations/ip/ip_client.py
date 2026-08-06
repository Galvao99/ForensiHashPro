from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

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
    """
    Cliente responsável por consultar a API IP2Location.io
    e normalizar o retorno para IpLookupResult.
    """

    BASE_URL = "https://api.ip2location.io/"

    def __init__(
        self,
        api_key: str,
        timeout: int = 15,
    ) -> None:
        self.api_key = api_key.strip()
        self.timeout = timeout

    def lookup(
        self,
        ip: str,
    ) -> IpLookupResult:
        if not self.api_key:
            raise MissingIpApiKeyError(
                "API Key da IP2Location não configurada."
            )

        normalized_ip = ip.strip()

        if not normalized_ip:
            raise InvalidIpLookupError(
                "Endereço IP não informado."
            )

        try:
            response = requests.get(
                self.BASE_URL,
                params={
                    "key": self.api_key,
                    "ip": normalized_ip,
                    "format": "json",
                },
                timeout=self.timeout,
            )

        except requests.Timeout as exc:
            raise InvalidIpLookupError(
                "Tempo limite excedido durante a consulta de IP."
            ) from exc

        except requests.RequestException as exc:
            raise InvalidIpLookupError(
                f"Falha de comunicação com a API: {exc}"
            ) from exc

        data = self._read_json(response)

        if (
            response.status_code == 429
            or self._contains_rate_limit_error(data)
        ):
            raise IpRateLimitError(
                "Limite de consultas da API atingido."
            )

        if response.status_code != 200:
            error_message = self._extract_error_message(data)

            raise InvalidIpLookupError(
                error_message
                or (
                    "Falha na consulta de IP. "
                    f"Status HTTP: {response.status_code}"
                )
            )

        if data.get("error"):
            raise InvalidIpLookupError(
                self._extract_error_message(data)
                or "A API retornou um erro não identificado."
            )

        return self._build_result(
            requested_ip=normalized_ip,
            data=data,
        )

    def _build_result(
        self,
        *,
        requested_ip: str,
        data: dict[str, Any],
    ) -> IpLookupResult:
        returned_ip = str(
            data.get("ip") or requested_ip
        ).strip()

        proxy_data = self._get_dict(
            data.get("proxy")
        )

        as_data = self._get_dict(
            data.get("as")
        )

        mobile_data = self._get_dict(
            data.get("mobile")
        )

        proxy_type = self._first_text(
            proxy_data.get("proxy_type"),
            data.get("proxy_type"),
        )

        proxy_provider = self._first_text(
            proxy_data.get("provider"),
            data.get("proxy_provider"),
        )

        proxy_threat = self._first_text(
            proxy_data.get("threat"),
            data.get("proxy_threat"),
        )

        proxy_last_seen = self._to_int(
            self._first_value(
                proxy_data.get("last_seen"),
                data.get("proxy_last_seen"),
            )
        )

        fraud_score = self._to_int(
            self._first_value(
                proxy_data.get("fraud_score"),
                data.get("fraud_score"),
            )
        )

        is_proxy = self._to_bool(
            self._first_value(
                data.get("is_proxy"),
                proxy_data.get("is_proxy"),
            )
        )

        asn = self._first_text(
            data.get("asn"),
            as_data.get("asn"),
        )

        as_name = self._first_text(
            data.get("as"),
            data.get("as_name"),
            as_data.get("name"),
        )

        mobile_country_code = self._first_text(
            data.get("mcc"),
            data.get("mobile_country_code"),
            mobile_data.get("mcc"),
        )

        mobile_network_code = self._first_text(
            data.get("mnc"),
            data.get("mobile_network_code"),
            mobile_data.get("mnc"),
        )

        mobile_brand = self._first_text(
            data.get("mobile_brand"),
            data.get("mobile_carrier"),
            mobile_data.get("brand"),
            mobile_data.get("carrier"),
        )

        normalized_proxy_type = proxy_type.upper()

        return IpLookupResult(
            ip=returned_ip,
            provider="IP2Location.io",

            ip_version=(
                "IPv6"
                if ":" in returned_ip
                else "IPv4"
            ),
            network_type="Public",
            is_public=True,

            country_code=self._optional_text(
                data.get("country_code")
            ),
            country=self._optional_text(
                data.get("country_name")
            ),
            region=self._optional_text(
                data.get("region_name")
            ),
            district=self._optional_text(
                data.get("district")
            ),
            city=self._optional_text(
                data.get("city_name")
            ),
            latitude=self._to_float(
                data.get("latitude")
            ),
            longitude=self._to_float(
                data.get("longitude")
            ),
            zip_code=self._optional_text(
                data.get("zip_code")
            ),
            time_zone=self._optional_text(
                data.get("time_zone")
            ),

            isp=self._optional_text(
                data.get("isp")
            ),
            organization=self._optional_text(
                data.get("organization")
            ),
            domain=self._optional_text(
                data.get("domain")
            ),
            asn=asn or None,
            as_name=as_name or None,
            usage_type=self._optional_text(
                data.get("usage_type")
            ),
            address_type=self._optional_text(
                data.get("address_type")
            ),
            net_speed=self._optional_text(
                data.get("net_speed")
            ),

            idd_code=self._optional_text(
                data.get("idd_code")
            ),
            area_code=self._optional_text(
                data.get("area_code")
            ),
            mobile_country_code=(
                mobile_country_code or None
            ),
            mobile_network_code=(
                mobile_network_code or None
            ),
            mobile_brand=mobile_brand or None,

            is_proxy=is_proxy,
            proxy_type=proxy_type or None,
            proxy_provider=proxy_provider or None,
            proxy_last_seen=proxy_last_seen,
            proxy_threat=proxy_threat or None,
            fraud_score=fraud_score,
            provider_metric_name="fraud_score",
            provider_classification=proxy_threat or None,
            limitations=(
                "Geolocalização por IP é aproximada e não identifica pessoa ou dispositivo.",
                "A resposta representa a base do provedor no instante da consulta.",
                "IP dinâmico, móvel, compartilhado ou CGNAT exige correlação adicional.",
            ),

            is_vpn=(
                normalized_proxy_type == "VPN"
            ),
            is_tor=(
                normalized_proxy_type == "TOR"
            ),
            is_datacenter=(
                normalized_proxy_type == "DCH"
            ),
            is_residential_proxy=(
                normalized_proxy_type == "RES"
            ),

            lookup_timestamp=datetime.now(timezone.utc),
            lookup_performed=True,
            severity=self._calculate_severity(
                is_proxy=is_proxy,
                proxy_type=normalized_proxy_type,
                fraud_score=fraud_score,
                proxy_threat=proxy_threat,
            ),
            message=self._build_message(
                is_proxy=is_proxy,
                proxy_type=normalized_proxy_type,
                fraud_score=fraud_score,
            ),
            raw=data,
        )

    def _calculate_severity(
        self,
        *,
        is_proxy: bool | None,
        proxy_type: str,
        fraud_score: int | None,
        proxy_threat: str,
    ) -> str:
        if (
            is_proxy is True
            or proxy_type in {
                "VPN",
                "DCH",
                "PUB",
                "WEB",
                "RES",
            }
        ):
            return "warning"
        # Métricas e classificações do provedor são preservadas como dados de
        # origem, mas não determinam automaticamente a severidade interna.
        return "info"

    def _build_message(
        self,
        *,
        is_proxy: bool | None,
        proxy_type: str,
        fraud_score: int | None,
    ) -> str:
        messages: list[str] = []

        if is_proxy:
            messages.append("Proxy identificado")

        proxy_labels = {
            "VPN": "VPN identificada",
            "TOR": "Nó Tor identificado",
            "DCH": "Infraestrutura de data center identificada",
            "PUB": "Proxy público identificado",
            "WEB": "Web proxy identificado",
            "SES": "Robô de mecanismo de busca identificado",
            "AIC": "Crawler de inteligência artificial identificado",
            "RES": "Proxy residencial identificado",
        }

        if proxy_type in proxy_labels:
            messages.append(
                proxy_labels[proxy_type]
            )

        if fraud_score is not None:
            messages.append(
                f"Métrica fraud_score do provedor: {fraud_score}"
            )

        if not messages:
            return "Consulta de IP realizada com sucesso."

        return " • ".join(messages)

    def _read_json(
        self,
        response: requests.Response,
    ) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise InvalidIpLookupError(
                "A API retornou uma resposta inválida."
            ) from exc

        if not isinstance(data, dict):
            raise InvalidIpLookupError(
                "A API retornou uma estrutura inesperada."
            )

        return data

    def _contains_rate_limit_error(
        self,
        data: dict[str, Any],
    ) -> bool:
        error_text = self._extract_error_message(
            data
        ).lower()

        return any(
            term in error_text
            for term in (
                "limit",
                "quota",
                "too many requests",
                "rate",
            )
        )

    def _extract_error_message(
        self,
        data: dict[str, Any],
    ) -> str:
        error = data.get("error")

        if isinstance(error, str):
            return error.strip()

        if isinstance(error, dict):
            for key in (
                "message",
                "error_message",
                "description",
            ):
                value = error.get(key)

                if value:
                    return str(value).strip()

        for key in (
            "message",
            "error_message",
            "description",
        ):
            value = data.get(key)

            if value:
                return str(value).strip()

        return ""

    def _get_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:
        if isinstance(value, dict):
            return value

        return {}

    def _first_value(
        self,
        *values: Any,
    ) -> Any:
        for value in values:
            if value not in {
                None,
                "",
            }:
                return value

        return None

    def _first_text(
        self,
        *values: Any,
    ) -> str:
        value = self._first_value(*values)

        if value is None:
            return ""

        return str(value).strip()

    def _optional_text(
        self,
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        normalized = str(value).strip()

        return normalized or None

    def _to_float(
        self,
        value: Any,
    ) -> float | None:
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(
        self,
        value: Any,
    ) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _to_bool(
        self,
        value: Any,
    ) -> bool | None:
        if isinstance(value, bool):
            return value

        if isinstance(value, int):
            return bool(value)

        if isinstance(value, str):
            normalized = value.strip().lower()

            if normalized in {
                "true",
                "yes",
                "sim",
                "1",
            }:
                return True

            if normalized in {
                "false",
                "no",
                "não",
                "nao",
                "0",
            }:
                return False

        return None

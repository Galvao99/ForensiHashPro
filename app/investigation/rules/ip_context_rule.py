from ipaddress import ip_address
from typing import Any

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    danger_badge,
    info_badge,
    neutral_badge,
    success_badge,
    warning_badge,
)


class IpContextRule(BaseCorrelationRule):
    """
    Analisa o contexto técnico dos endereços IP identificados.

    A regra trabalha tanto com IPs apenas detectados no conteúdo
    quanto com resultados enriquecidos obtidos pela API.
    """

    rule_id = "ip_context"
    name = "Contexto dos endereços IP"

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        file_names = set(context.detected_ips)
        file_names.update(context.ip_results)

        for file_name in sorted(file_names):
            detected_ips = context.detected_ips.get(
                file_name,
                [],
            )

            enriched_results = context.ip_results.get(
                file_name,
                [],
            )

            enriched_by_ip = {
                self._get_text(result, "ip"): result
                for result in enriched_results
                if self._get_text(result, "ip")
            }

            processed_ips: set[str] = set()

            for ip_value in detected_ips:
                normalized_ip = str(ip_value).strip()

                if not normalized_ip:
                    continue

                processed_ips.add(normalized_ip)

                enriched_result = enriched_by_ip.get(
                    normalized_ip
                )

                if enriched_result is not None:
                    self._analyze_enriched_ip(
                        findings=findings,
                        file_name=file_name,
                        result=enriched_result,
                    )

                    continue

                self._analyze_basic_ip(
                    findings=findings,
                    file_name=file_name,
                    ip_value=normalized_ip,
                )

            for ip_value, enriched_result in enriched_by_ip.items():
                if ip_value in processed_ips:
                    continue

                self._analyze_enriched_ip(
                    findings=findings,
                    file_name=file_name,
                    result=enriched_result,
                )

        return findings

    # ------------------------------------------------------------------
    # Análise básica
    # ------------------------------------------------------------------

    def _analyze_basic_ip(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        ip_value: str,
    ) -> None:
        try:
            parsed_ip = ip_address(ip_value)

        except ValueError:
            self.add_warning(
                findings,
                title="Endereço IP inválido",
                description=(
                    "O valor identificado não apresenta estrutura "
                    "compatível com um endereço IP válido."
                ),
                icon="network-warning",
                source_file=file_name,
                badges=[
                    warning_badge("IP inválido"),
                    neutral_badge(ip_value),
                    neutral_badge(file_name),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "valido": False,
                },
            )

            return

        ip_version = f"IPv{parsed_ip.version}"

        if parsed_ip.is_loopback:
            self.add_warning(
                findings,
                title="IP de loopback identificado",
                description=(
                    "O endereço representa o próprio dispositivo "
                    "e não identifica uma conexão externa."
                ),
                icon="network-loopback",
                source_file=file_name,
                badges=[
                    warning_badge("Loopback"),
                    info_badge(ip_version),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "versao": ip_version,
                    "tipo": "Loopback",
                    "publico": False,
                },
            )

            return

        if parsed_ip.is_private:
            self.add_warning(
                findings,
                title="IP privado identificado",
                description=(
                    "O endereço pertence a uma faixa privada e não "
                    "permite geolocalização pública direta."
                ),
                icon="network-private",
                source_file=file_name,
                badges=[
                    warning_badge("IP privado"),
                    info_badge(ip_version),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "versao": ip_version,
                    "tipo": "Private",
                    "publico": False,
                },
            )

            return

        if parsed_ip.is_unspecified:
            self.add_warning(
                findings,
                title="IP não especificado",
                description=(
                    "O endereço representa uma origem não especificada "
                    "e não identifica um ponto externo de acesso."
                ),
                icon="network-warning",
                source_file=file_name,
                badges=[
                    warning_badge("Não especificado"),
                    info_badge(ip_version),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "versao": ip_version,
                    "tipo": "Unspecified",
                    "publico": False,
                },
            )

            return

        if parsed_ip.is_multicast:
            self.add_warning(
                findings,
                title="IP multicast identificado",
                description=(
                    "O endereço pertence a uma faixa multicast e não "
                    "representa diretamente um dispositivo de origem."
                ),
                icon="network-warning",
                source_file=file_name,
                badges=[
                    warning_badge("Multicast"),
                    info_badge(ip_version),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "versao": ip_version,
                    "tipo": "Multicast",
                    "publico": False,
                },
            )

            return

        if parsed_ip.is_reserved:
            self.add_warning(
                findings,
                title="IP reservado identificado",
                description=(
                    "O endereço pertence a uma faixa reservada e não "
                    "possui aplicação direta para geolocalização pública."
                ),
                icon="network-warning",
                source_file=file_name,
                badges=[
                    warning_badge("Reservado"),
                    info_badge(ip_version),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "versao": ip_version,
                    "tipo": "Reserved",
                    "publico": False,
                },
            )

            return

        self.add_info(
            findings,
            title="IP público identificado",
            description=(
                "O endereço apresenta estrutura pública e pode ser "
                "submetido a consulta de contexto de rede."
            ),
            icon="network",
            source_file=file_name,
            badges=[
                success_badge("IP público"),
                info_badge(ip_version),
                neutral_badge(ip_value),
            ],
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "versao": ip_version,
                "tipo": "Public",
                "publico": True,
            },
        )

    # ------------------------------------------------------------------
    # Análise enriquecida
    # ------------------------------------------------------------------

    def _analyze_enriched_ip(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
    ) -> None:
        ip_value = self._get_text(
            result,
            "ip",
        )

        if not ip_value:
            return

        ip_version = self._get_text(
            result,
            "ip_version",
            "IP",
        )

        network_type = self._get_text(
            result,
            "network_type",
        )

        is_public = self._get_bool(
            result,
            "is_public",
        )

        lookup_performed = self._get_bool(
            result,
            "lookup_performed",
        )

        if lookup_performed is False:
            self._add_lookup_not_performed_finding(
                findings=findings,
                file_name=file_name,
                result=result,
                ip_value=ip_value,
                ip_version=ip_version,
                network_type=network_type,
            )

            return

        if is_public is False or network_type.lower() in {
            "private",
            "loopback",
            "reserved",
            "unspecified",
            "multicast",
            "não aplicável",
        }:
            self._add_non_public_finding(
                findings=findings,
                file_name=file_name,
                result=result,
                ip_value=ip_value,
                ip_version=ip_version,
                network_type=network_type,
            )

            return

        self._add_public_ip_finding(
            findings=findings,
            file_name=file_name,
            result=result,
            ip_value=ip_value,
            ip_version=ip_version,
            network_type=network_type,
        )

        self._analyze_network_provider(
            findings=findings,
            file_name=file_name,
            result=result,
            ip_value=ip_value,
        )

        self._analyze_location(
            findings=findings,
            file_name=file_name,
            result=result,
            ip_value=ip_value,
        )

        self._analyze_mobile_network(
            findings=findings,
            file_name=file_name,
            result=result,
            ip_value=ip_value,
        )

        self._analyze_risk_indicators(
            findings=findings,
            file_name=file_name,
            result=result,
            ip_value=ip_value,
        )

    def _add_lookup_not_performed_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
        ip_version: str,
        network_type: str,
    ) -> None:
        message = self._get_text(
            result,
            "message",
            "Consulta externa não realizada.",
        )

        badges = [
            warning_badge("Consulta não realizada"),
            neutral_badge(ip_value),
        ]

        if ip_version:
            badges.append(
                info_badge(ip_version)
            )

        if network_type:
            badges.append(
                neutral_badge(network_type)
            )

        self.add_warning(
            findings,
            title="Consulta externa de IP não realizada",
            description=message,
            icon="network-warning",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "versao": ip_version,
                "tipo": network_type,
                "consulta_realizada": False,
                "mensagem": message,
            },
        )

    def _add_non_public_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
        ip_version: str,
        network_type: str,
    ) -> None:
        display_type = (
            network_type
            or "Não público"
        )

        message = self._get_text(
            result,
            "message",
        )

        description = (
            message
            or (
                "O endereço não é publicamente roteável e não "
                "permite atribuição geográfica externa direta."
            )
        )

        self.add_warning(
            findings,
            title="IP sem aplicação geográfica pública",
            description=description,
            icon="network-private",
            source_file=file_name,
            badges=[
                warning_badge(display_type),
                info_badge(ip_version),
                neutral_badge(ip_value),
            ],
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "versao": ip_version,
                "tipo": display_type,
                "publico": False,
                "consulta_realizada": self._get_bool(
                    result,
                    "lookup_performed",
                ),
                "mensagem": message,
            },
        )

    def _add_public_ip_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
        ip_version: str,
        network_type: str,
    ) -> None:
        provider = self._get_text(
            result,
            "provider",
        )

        lookup_timestamp = self._get_value(
            result,
            "lookup_timestamp",
        )

        badges = [
            success_badge("IP público"),
            info_badge(ip_version),
            neutral_badge(ip_value),
        ]

        if network_type:
            badges.append(
                neutral_badge(network_type)
            )

        if provider:
            badges.append(
                neutral_badge(provider)
            )

        self.add_ok(
            findings,
            title="IP público analisado",
            description=(
                "O endereço é publicamente roteável e apresentou "
                "informações de contexto de rede."
            ),
            icon="network",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "versao": ip_version,
                "tipo": network_type,
                "publico": True,
                "provider": provider,
                "consulta_realizada": True,
                "data_consulta": self._serialize_value(
                    lookup_timestamp
                ),
            },
        )

    # ------------------------------------------------------------------
    # Rede
    # ------------------------------------------------------------------

    def _analyze_network_provider(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
    ) -> None:
        isp = self._get_text(
            result,
            "isp",
        )

        organization = self._get_text(
            result,
            "organization",
        )

        asn = self._get_text(
            result,
            "asn",
        )

        as_name = self._get_text(
            result,
            "as_name",
        )

        domain = self._get_text(
            result,
            "domain",
        )

        usage_type = self._get_text(
            result,
            "usage_type",
        )

        address_type = self._get_text(
            result,
            "address_type",
        )

        net_speed = self._get_text(
            result,
            "net_speed",
        )

        if not any(
            (
                isp,
                organization,
                asn,
                as_name,
                domain,
                usage_type,
                address_type,
                net_speed,
            )
        ):
            return

        badges = []

        if isp:
            badges.append(
                info_badge(isp)
            )

        if organization and organization != isp:
            badges.append(
                neutral_badge(organization)
            )

        if asn:
            normalized_asn = (
                asn
                if asn.upper().startswith("AS")
                else f"AS{asn}"
            )

            badges.append(
                neutral_badge(normalized_asn)
            )

        if as_name:
            badges.append(
                neutral_badge(as_name)
            )

        if usage_type:
            badges.append(
                info_badge(usage_type)
            )

        if address_type:
            badges.append(
                neutral_badge(address_type)
            )

        if domain:
            badges.append(
                neutral_badge(domain)
            )

        if net_speed:
            badges.append(
                neutral_badge(net_speed)
            )

        self.add_info(
            findings,
            title="Contexto de rede identificado",
            description=(
                "Foram identificadas informações sobre a rede "
                "responsável pelo endereço IP."
            ),
            icon="network-provider",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "isp": isp,
                "organizacao": organization,
                "asn": asn,
                "nome_as": as_name,
                "dominio": domain,
                "tipo_de_uso": usage_type,
                "tipo_de_endereco": address_type,
                "velocidade_de_rede": net_speed,
            },
        )

    # ------------------------------------------------------------------
    # Localização
    # ------------------------------------------------------------------

    def _analyze_location(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
    ) -> None:
        country_code = self._get_text(
            result,
            "country_code",
        )

        country = self._get_text(
            result,
            "country",
        )

        region = self._get_text(
            result,
            "region",
        )

        district = self._get_text(
            result,
            "district",
        )

        city = self._get_text(
            result,
            "city",
        )

        zip_code = self._get_text(
            result,
            "zip_code",
        )

        time_zone = self._get_text(
            result,
            "time_zone",
        )

        latitude = self._get_value(
            result,
            "latitude",
        )

        longitude = self._get_value(
            result,
            "longitude",
        )

        if not any(
            (
                country_code,
                country,
                region,
                district,
                city,
                zip_code,
                time_zone,
                latitude is not None,
                longitude is not None,
            )
        ):
            return

        location_parts = [
            value
            for value in (
                city,
                district,
                region,
                country,
            )
            if value
        ]

        location_summary = " • ".join(
            location_parts
        )

        badges = []

        if city:
            badges.append(
                info_badge(city)
            )

        if district:
            badges.append(
                neutral_badge(district)
            )

        if region:
            badges.append(
                neutral_badge(region)
            )

        if country:
            badges.append(
                neutral_badge(country)
            )

        if country_code:
            badges.append(
                neutral_badge(country_code)
            )

        if time_zone:
            badges.append(
                neutral_badge(time_zone)
            )

        self.add_info(
            findings,
            title="Geolocalização aproximada do IP",
            description=(
                "A consulta apresentou localização aproximada "
                "associada à infraestrutura do endereço IP."
            ),
            icon="location",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "localizacao": location_summary,
                "codigo_pais": country_code,
                "pais": country,
                "regiao": region,
                "distrito": district,
                "cidade": city,
                "cep": zip_code,
                "fuso_horario": time_zone,
                "latitude": latitude,
                "longitude": longitude,
            },
        )

    # ------------------------------------------------------------------
    # Rede móvel
    # ------------------------------------------------------------------

    def _analyze_mobile_network(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
    ) -> None:
        idd_code = self._get_text(
            result,
            "idd_code",
        )

        area_code = self._get_text(
            result,
            "area_code",
        )

        mobile_country_code = self._get_text(
            result,
            "mobile_country_code",
        )

        mobile_network_code = self._get_text(
            result,
            "mobile_network_code",
        )

        mobile_brand = self._get_text(
            result,
            "mobile_brand",
        )

        if not any(
            (
                idd_code,
                area_code,
                mobile_country_code,
                mobile_network_code,
                mobile_brand,
            )
        ):
            return

        badges = []

        if mobile_brand:
            badges.append(
                info_badge(mobile_brand)
            )

        if mobile_country_code:
            badges.append(
                neutral_badge(
                    f"MCC {mobile_country_code}"
                )
            )

        if mobile_network_code:
            badges.append(
                neutral_badge(
                    f"MNC {mobile_network_code}"
                )
            )

        if idd_code:
            badges.append(
                neutral_badge(
                    f"DDI {idd_code}"
                )
            )

        if area_code:
            badges.append(
                neutral_badge(
                    f"Área {area_code}"
                )
            )

        self.add_info(
            findings,
            title="Contexto de rede móvel identificado",
            description=(
                "A consulta apresentou dados associados à rede "
                "móvel ou à telefonia da região."
            ),
            icon="mobile-network",
            source_file=file_name,
            badges=badges,
            metadata={
                "arquivo": file_name,
                "ip": ip_value,
                "codigo_ddi": idd_code,
                "codigo_area": area_code,
                "mcc": mobile_country_code,
                "mnc": mobile_network_code,
                "operadora_movel": mobile_brand,
            },
        )

    # ------------------------------------------------------------------
    # Risco e anonimização
    # ------------------------------------------------------------------

    def _analyze_risk_indicators(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        result: Any,
        ip_value: str,
    ) -> None:
        severity = self._get_text(
            result,
            "severity",
        ).lower()

        message = self._get_text(
            result,
            "message",
        )

        is_proxy = self._get_bool(
            result,
            "is_proxy",
        )

        is_vpn = self._get_bool(
            result,
            "is_vpn",
        )

        is_tor = self._get_bool(
            result,
            "is_tor",
        )

        is_datacenter = self._get_bool(
            result,
            "is_datacenter",
        )

        is_residential_proxy = self._get_bool(
            result,
            "is_residential_proxy",
        )

        proxy_type = self._get_text(
            result,
            "proxy_type",
        )

        proxy_provider = self._get_text(
            result,
            "proxy_provider",
        )

        proxy_last_seen = self._get_value(
            result,
            "proxy_last_seen",
        )

        proxy_threat = self._get_text(
            result,
            "proxy_threat",
        )

        fraud_score = self._get_value(
            result,
            "fraud_score",
        )

        risk_badges = []
        risk_metadata: dict[str, Any] = {
            "arquivo": file_name,
            "ip": ip_value,
        }

        if is_datacenter:
            risk_badges.append(
                warning_badge("Data Center")
            )

            risk_metadata["data_center"] = True

        if is_proxy:
            risk_badges.append(
                warning_badge("Proxy")
            )

            risk_metadata["proxy"] = True

        if is_vpn:
            risk_badges.append(
                warning_badge("VPN")
            )

            risk_metadata["vpn"] = True

        if is_tor:
            risk_badges.append(
                danger_badge("Tor")
            )

            risk_metadata["tor"] = True

        if is_residential_proxy:
            risk_badges.append(
                warning_badge("Proxy residencial")
            )

            risk_metadata["proxy_residencial"] = True

        if proxy_type:
            risk_badges.append(
                neutral_badge(proxy_type)
            )

            risk_metadata["tipo_proxy"] = proxy_type

        if proxy_provider:
            risk_badges.append(
                neutral_badge(proxy_provider)
            )

            risk_metadata["provedor_proxy"] = proxy_provider

        if proxy_last_seen is not None:
            risk_badges.append(
                neutral_badge(
                    f"Última detecção: {proxy_last_seen}"
                )
            )

            risk_metadata["ultima_deteccao_proxy"] = (
                proxy_last_seen
            )

        if proxy_threat:
            risk_badges.append(
                danger_badge(proxy_threat)
            )

            risk_metadata["ameaca_proxy"] = proxy_threat

        if fraud_score is not None:
            risk_badges.append(
                neutral_badge(
                    f"Métrica do provedor: {fraud_score}"
                )
            )

            risk_metadata["metrica_provedor_fraud_score"] = fraud_score

        if severity in {
            "warning",
            "critical",
        }:
            risk_badges.append(
                warning_badge(
                    severity.upper()
                )
            )

            risk_metadata["severidade_api"] = severity

        if message:
            risk_metadata["mensagem_api"] = message

        if not risk_badges:
            self.add_ok(
                findings,
                title="Sem indicadores adicionais de risco",
                description=(
                    "A consulta não apresentou indicadores de proxy, "
                    "VPN, Tor ou data center na resposta consultada. "
                    "Isso não comprova ausência de mascaramento."
                ),
                icon="network-check",
                source_file=file_name,
                badges=[
                    success_badge("Sem indicadores"),
                    neutral_badge(ip_value),
                ],
                metadata={
                    "arquivo": file_name,
                    "ip": ip_value,
                    "severidade_api": severity or "ok",
                    "mensagem_api": message,
                },
            )

            return

        self.add_warning(
            findings,
            title="Indicadores de atenção associados ao IP",
            description=(
                message
                or (
                    "O endereço apresentou características que "
                    "recomendam avaliação contextual adicional."
                )
            ),
            icon="network-warning",
            source_file=file_name,
            badges=risk_badges,
            metadata=risk_metadata,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_value(
        self,
        target: Any,
        attribute: str,
        default: Any = None,
    ) -> Any:
        if isinstance(target, dict):
            return target.get(
                attribute,
                default,
            )

        return getattr(
            target,
            attribute,
            default,
        )

    def _get_text(
        self,
        target: Any,
        attribute: str,
        default: str = "",
    ) -> str:
        value = self._get_value(
            target,
            attribute,
            default,
        )

        if value is None:
            return default

        return str(value).strip()

    def _get_bool(
        self,
        target: Any,
        attribute: str,
    ) -> bool | None:
        value = self._get_value(
            target,
            attribute,
        )

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

    def _serialize_value(
        self,
        value: Any,
    ) -> Any:
        if value is None:
            return None

        isoformat = getattr(
            value,
            "isoformat",
            None,
        )

        if callable(isoformat):
            return isoformat()

        return value

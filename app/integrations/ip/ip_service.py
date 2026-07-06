import ipaddress

from app.integrations.ip.ip_exceptions import InvalidIpLookupError
from app.integrations.ip.ip_models import IpLookupResult
from app.integrations.ip.ip_parser import IpParser
from app.integrations.ip.ip_provider import IpProvider
from app.settings import SettingsService


class IpAnalysisService:
    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self.settings_service = settings_service or SettingsService()

    def analyze(self, ip: str) -> IpLookupResult:
        cleaned_ip = ip.strip()

        if not self._is_valid_ip(cleaned_ip):
            raise InvalidIpLookupError("O IP informado é inválido.")

        if not self._is_public_ip(cleaned_ip):
            return self._build_non_public_result(cleaned_ip)

        settings = self.settings_service.load()
        client = IpProvider(settings).get_client()

        return client.lookup(cleaned_ip)

    def analyze_text(self, text: str) -> list[IpLookupResult]:
        ips = IpParser.extract_all(text)
        results: list[IpLookupResult] = []

        for ip in ips:
            try:
                results.append(self.analyze(ip))
            except Exception as error:
                results.append(
                    IpLookupResult(
                        ip=ip,
                        lookup_performed=False,
                        severity="error",
                        message=f"Não foi possível analisar o IP: {error}",
                    )
                )

        return results

    def _is_valid_ip(self, ip: str) -> bool:
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False

    def _is_public_ip(self, ip: str) -> bool:
        return ipaddress.ip_address(ip).is_global

    def _build_non_public_result(self, ip: str) -> IpLookupResult:
        parsed = ipaddress.ip_address(ip)

        if parsed.is_private:
            message = (
                "O endereço IP identificado pertence a uma faixa privada, "
                "utilizada em redes internas. Não é roteável na Internet pública "
                "e não permite consulta externa de geolocalização."
            )
            severity = "warning"

        elif parsed.is_loopback:
            message = (
                "O endereço IP identificado é de loopback, utilizado pelo próprio "
                "dispositivo local. Não representa acesso externo."
            )
            severity = "warning"

        elif parsed.is_link_local:
            message = (
                "O endereço IP identificado é link-local, utilizado em comunicação "
                "local da rede, sem roteamento público."
            )
            severity = "warning"

        elif parsed.is_reserved:
            message = (
                "O endereço IP identificado pertence a faixa reservada, sem uso "
                "regular para geolocalização pública."
            )
            severity = "warning"

        elif parsed.is_multicast:
            message = (
                "O endereço IP identificado pertence a faixa multicast, não sendo "
                "atribuído a um usuário/dispositivo individual para fins de geolocalização."
            )
            severity = "warning"

        else:
            message = (
                "O endereço IP identificado não é roteável publicamente, razão pela qual "
                "não foi realizada consulta externa de geolocalização."
            )
            severity = "warning"

        return IpLookupResult(
            ip=str(parsed),
            provider="Análise local",
            lookup_performed=False,
            severity=severity,
            message=message,
        )
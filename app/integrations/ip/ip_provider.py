from app.integrations.ip.ip_client import BaseIpClient, Ip2LocationClient
from app.integrations.ip.ip_exceptions import UnsupportedIpProviderError
from app.settings.settings_model import AppSettings


class IpProvider:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def get_client(self) -> BaseIpClient:
        provider = self.settings.ip_provider.lower().strip()

        if provider == "ip2location":
            return Ip2LocationClient(
                api_key=self.settings.ip_api_key,
                timeout=self.settings.request_timeout,
            )

        raise UnsupportedIpProviderError(
            f"Provider de IP não suportado: {self.settings.ip_provider}"
        )
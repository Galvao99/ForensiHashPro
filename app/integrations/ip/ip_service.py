import ipaddress

from app.integrations.ip.ip_exceptions import (
    InvalidIpLookupError,
    IpIntegrationError,
    IpNetworkUnavailableError,
    IpProviderError,
    IpRateLimitError,
    IpTimeoutError,
    MissingIpApiKeyError,
)
from app.integrations.ip.ip_models import IpLookupResult
from app.integrations.ip.ip_parser import IpParser
from app.integrations.ip.ip_provider import IpProvider
from app.settings import SettingsService
from app.settings import InvalidConfigurationError
from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)


class IpAnalysisService:
    def __init__(self, settings_service: SettingsService | None = None) -> None:
        self.settings_service = settings_service or SettingsService()

    def analyze(self, ip: str) -> IpLookupResult:
        """API legada: preserva exceções para consumidores existentes."""
        cleaned_ip = ip.strip()

        if not self._is_valid_ip(cleaned_ip):
            raise InvalidIpLookupError("O IP informado é inválido.")

        if not self._is_public_ip(cleaned_ip):
            return self._build_non_public_result(cleaned_ip)

        settings = self.settings_service.load()
        client = IpProvider(settings).get_client()

        return client.lookup(cleaned_ip)

    def analyze_step(self, ip: str) -> StepResult[IpLookupResult]:
        """Executa a consulta com estado de processamento explícito."""
        cleaned_ip = ip.strip()
        if not self._is_valid_ip(cleaned_ip):
            return self._failure(
                cleaned_ip, ProcessingStatus.FAILED, "ip_invalid",
                "O endereço IP informado é inválido.", InvalidIpLookupError(),
            )
        try:
            if not self._is_public_ip(cleaned_ip):
                return self._step(
                    ProcessingStatus.SUCCESS,
                    "Classificação local de IP concluída.",
                    self._build_non_public_result(cleaned_ip),
                )
            settings = self.settings_service.load()
            if not settings.ip_lookup_enabled:
                return self._failure(
                    cleaned_ip, ProcessingStatus.UNAVAILABLE,
                    "ip_integration_disabled",
                    "A integração de contexto de IP está desabilitada.",
                    MissingIpApiKeyError(),
                )
            result = IpProvider(settings).get_client().lookup(cleaned_ip)
        except (MissingIpApiKeyError, InvalidConfigurationError) as error:
            return self._failure(
                cleaned_ip, ProcessingStatus.UNAVAILABLE, "ip_key_missing",
                "A credencial do provedor de IP não está configurada.", error,
            )
        except IpTimeoutError as error:
            return self._failure(
                cleaned_ip, ProcessingStatus.FAILED, "ip_timeout",
                "A consulta de IP excedeu o tempo máximo.", error,
            )
        except IpNetworkUnavailableError as error:
            return self._failure(
                cleaned_ip, ProcessingStatus.UNAVAILABLE, "ip_network_unavailable",
                "A rede ou o provedor de IP está indisponível.", error,
            )
        except IpRateLimitError as error:
            return self._failure(
                cleaned_ip, ProcessingStatus.UNAVAILABLE, "ip_rate_limit",
                "O limite de consultas do provedor foi atingido.", error,
            )
        except (IpProviderError, IpIntegrationError) as error:
            return self._failure(
                cleaned_ip, ProcessingStatus.FAILED, "ip_provider_error",
                "O provedor não concluiu a consulta de IP.", error,
            )
        return self._step(ProcessingStatus.SUCCESS, "Consulta de IP concluída.", result)

    @staticmethod
    def _failure(
        ip: str,
        status: ProcessingStatus,
        code: str,
        message: str,
        error: BaseException,
    ) -> StepResult[IpLookupResult]:
        issue = ProcessingIssue(
            code=code,
            status=status,
            technical_message=message,
            user_message=message,
            component="ip",
            details={"error_type": type(error).__name__},
            impact=ProcessingImpact.COMPONENT_ONLY,
            original_exception=error,
        )
        value = IpLookupResult(
            ip=ip,
            lookup_performed=False,
            severity=(
                "warning"
                if status is ProcessingStatus.UNAVAILABLE
                else "error"
            ),
            message=message,
        )
        return IpAnalysisService._step(status, message, value, [issue])

    @staticmethod
    def _step(
        status: ProcessingStatus,
        message: str,
        value: IpLookupResult,
        issues: list[ProcessingIssue] | None = None,
    ) -> StepResult[IpLookupResult]:
        return StepResult(
            code="ip_lookup",
            component="ip",
            status=status,
            technical_message=message,
            user_message=message,
            value=value,
            issues=issues or [],
        )

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

    def analyze_text_steps(self, text: str) -> list[StepResult[IpLookupResult]]:
        """Versão estruturada que não confunde falha de rede com lista vazia."""
        return [self.analyze_step(ip) for ip in IpParser.extract_all(text)]

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

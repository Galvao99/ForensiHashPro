from dataclasses import dataclass, field
from app.settings.processing_limits import ProcessingLimits


class InvalidConfigurationError(ValueError):
    """Configuração fornecida é inconsistente ou insegura."""

@dataclass
class AppSettings:
    ip_provider: str = "ip2location"
    ip_api_key: str = field(default="", repr=False)
    ip_lookup_enabled: bool = False
    request_timeout: int = 15
    ocr_enabled: bool = True
    metadata_enabled: bool = True
    rust_json_enabled: bool = True
    limits: ProcessingLimits = field(default_factory=ProcessingLimits)

    def validate(self) -> None:
        if not 1 <= self.request_timeout <= 120:
            raise InvalidConfigurationError(
                "request_timeout deve estar entre 1 e 120 segundos."
            )
        if self.ip_lookup_enabled and self.ip_provider.strip().lower() != "ip2location":
            raise InvalidConfigurationError(
                f"Provider de IP não suportado: {self.ip_provider}"
            )
        if self.ip_lookup_enabled and not self.ip_api_key.strip():
            raise InvalidConfigurationError(
                "IP2Location está habilitado, mas IP2LOCATION_API_KEY não foi definida."
            )
        self.limits.validate()

    def safe_dict(self) -> dict[str, object]:
        """Serializa somente configuração não secreta."""
        return {
            "ip_provider": self.ip_provider,
            "ip_lookup_enabled": self.ip_lookup_enabled,
            "request_timeout": self.request_timeout,
            "ocr_enabled": self.ocr_enabled,
            "metadata_enabled": self.metadata_enabled,
            "rust_json_enabled": self.rust_json_enabled,
            "limits": {
                name: getattr(self.limits, name)
                for name in self.limits.__dataclass_fields__
            },
        }

from dataclasses import dataclass

@dataclass(frozen=True)
class DigitalSignatureResult:
    """Resultado da análise de assinatura digital."""

    has_signature: bool
    signature_count: int = 0
    signer: str | None = None
    issuer: str | None = None
    serial_number: str | None = None
    algorithm: str | None = None
    signing_time: str | None = None
    timestamp: str | None = None   # mantém
    valid_from: str | None = None
    valid_until: str | None = None
    technical_status: str = "Não analisado"
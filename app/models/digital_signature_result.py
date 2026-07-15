from dataclasses import dataclass
from enum import Enum


class SignatureAnalysisStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    ERROR = "error"

@dataclass(frozen=True)
class DigitalSignatureResult:
    """Resultado da análise de assinatura digital."""

    has_signature: bool | None
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
    analysis_status: SignatureAnalysisStatus | None = None
    error_code: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        if self.analysis_status is not None:
            return

        inferred_status = (
            SignatureAnalysisStatus.PRESENT
            if self.has_signature is True
            else SignatureAnalysisStatus.ABSENT
            if self.has_signature is False
            else SignatureAnalysisStatus.NOT_APPLICABLE
        )
        object.__setattr__(
            self,
            "analysis_status",
            inferred_status,
        )

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SignatureAnalysisStatus(str, Enum):
    PRESENT = "present"
    ABSENT = "absent"
    NOT_APPLICABLE = "not_applicable"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


class SignatureValidationStatus(str, Enum):
    NOT_PERFORMED = "not_performed"
    VALID = "valid"
    INVALID = "invalid"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True, slots=True)
class SignatureLocator:
    field_name: str | None = None
    object_number: int | None = None
    object_generation: int | None = None
    signed_revision: int | None = None
    byte_range: tuple[int, ...] = ()
    embedded_index: int | None = None

    @property
    def canonical(self) -> str:
        parts: list[str] = []
        if self.field_name:
            parts.append(f"signature_field:{self.field_name}")
        if self.object_number is not None:
            generation = self.object_generation if self.object_generation is not None else 0
            parts.append(f"pdf_object:{self.object_number}:{generation}")
        if self.signed_revision is not None:
            parts.append(f"signed_revision:{self.signed_revision}")
        if self.byte_range:
            parts.append("byte_range:" + ",".join(str(value) for value in self.byte_range))
        if not parts and self.embedded_index is not None:
            parts.append(f"embedded_signature:{self.embedded_index}")
        return "|".join(parts)


@dataclass(frozen=True, slots=True)
class CertificateIdentity:
    certificate_id: str
    fingerprint_sha256: str
    fingerprint_source: str = "sha256_der"
    subject: str | None = None
    issuer: str | None = None
    serial_number: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(frozen=True, slots=True)
class SignatureRecord:
    signature_id: str
    locator: SignatureLocator
    certificate: CertificateIdentity | None = None
    algorithm: str | None = None
    signing_time: str | None = None
    trusted_timestamp: str | None = None
    signature_type: str | None = None
    validation_status: SignatureValidationStatus = SignatureValidationStatus.NOT_PERFORMED


@dataclass(frozen=True, slots=True)
class SignatureParseIssue:
    embedded_index: int
    locator: str
    code: str
    error_type: str
    message: str


@dataclass(frozen=True, slots=True)
class DigitalSignatureResult:
    """Canonical signature collection with a compatible first-record projection."""

    has_signature: bool | None
    signature_count: int = 0
    signer: str | None = None
    issuer: str | None = None
    serial_number: str | None = None
    algorithm: str | None = None
    signing_time: str | None = None
    timestamp: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    technical_status: str = "Não analisado"
    analysis_status: SignatureAnalysisStatus | None = None
    error_code: str | None = None
    error_message: str | None = None
    validation_status: SignatureValidationStatus = SignatureValidationStatus.NOT_PERFORMED
    signatures: tuple[SignatureRecord, ...] = ()
    signature_errors: tuple[SignatureParseIssue, ...] = ()

    def __post_init__(self) -> None:
        if self.signatures:
            first = self.signatures[0]
            certificate = first.certificate
            projection = {
                "signature_count": self.signature_count or len(self.signatures),
                "signer": self.signer or (certificate.subject if certificate else None),
                "issuer": self.issuer or (certificate.issuer if certificate else None),
                "serial_number": self.serial_number or (
                    certificate.serial_number if certificate else None
                ),
                "algorithm": self.algorithm or first.algorithm,
                "signing_time": self.signing_time or first.signing_time,
                "timestamp": self.timestamp or first.trusted_timestamp,
                "valid_from": self.valid_from or (certificate.valid_from if certificate else None),
                "valid_until": self.valid_until or (certificate.valid_until if certificate else None),
            }
            for field, value in projection.items():
                object.__setattr__(self, field, value)
        if self.analysis_status is None:
            inferred_status = (
                SignatureAnalysisStatus.PRESENT
                if self.has_signature is True
                else SignatureAnalysisStatus.ABSENT
                if self.has_signature is False
                else SignatureAnalysisStatus.NOT_APPLICABLE
            )
            object.__setattr__(self, "analysis_status", inferred_status)

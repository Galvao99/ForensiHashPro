from dataclasses import dataclass

from app.models.digital_signature_result import (
    SignatureAnalysisStatus,
)


@dataclass(frozen=True, slots=True)
class IntegrityResult:
    """
    Resultado da avaliação de integridade estrutural do arquivo.

    Alguns campos ficam como None porque serão preenchidos na V2.
    """

    # Campo legado mantido para compatibilidade de serialização. O score
    # agregado foi desativado porque combinava dimensões independentes e
    # penalizava ausências que não demonstram perda de integridade.
    score: int | None
    technical_status: str

    is_structurally_valid: bool | None
    hash_verified: bool
    magic_number_verified: bool
    digital_signature_present: bool | None
    digital_signature_analysis_status: (
        SignatureAnalysisStatus | None
    ) = None
    digital_signature_error: str | None = None

    header_valid: bool | None = None
    eof_valid: bool | None = None
    multiple_eof: bool | None = None
    encrypted: bool | None = None
    javascript_detected: bool | None = None
    embedded_files: bool | None = None
    xref_valid: bool | None = None
    trailer_valid: bool | None = None
    incremental_updates: int | None = None

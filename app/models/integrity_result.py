from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityResult:
    """
    Resultado da avaliação de integridade estrutural do arquivo.

    Alguns campos ficam como None porque serão preenchidos na V2.
    """

    score: int
    technical_status: str

    is_structurally_valid: bool
    hash_verified: bool
    magic_number_verified: bool
    digital_signature_present: bool

    header_valid: bool | None = None
    eof_valid: bool | None = None
    multiple_eof: bool | None = None
    encrypted: bool | None = None
    javascript_detected: bool | None = None
    embedded_files: bool | None = None
    xref_valid: bool | None = None
    trailer_valid: bool | None = None
    incremental_updates: int | None = None
from dataclasses import dataclass


@dataclass(frozen=True)
class IntegrityResult:
    """
    Resultado da avaliação de integridade estrutural do arquivo.
    """

    score: int

    is_structurally_valid: bool
    hash_verified: bool
    magic_number_verified: bool
    digital_signature_present: bool
    technical_status: str
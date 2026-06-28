from dataclasses import dataclass


@dataclass(frozen=True)
class MagicNumberResult:
    """Resultado da identificação por assinatura binária."""

    detected_type: str

    signature: str

    extension_matches: bool
from dataclasses import dataclass


@dataclass(frozen=True)
class Reference:
    """
    Representa uma referência técnica, normativa ou jurídica
    relacionada a um achado pericial.
    """

    title: str
    description: str
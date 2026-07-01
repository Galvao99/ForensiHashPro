from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationItem:
    """
    Representa um item avaliado
    por um motor pericial.
    """

    title: str
    passed: bool
    description: str
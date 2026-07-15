from __future__ import annotations

import re
import unicodedata
from typing import Final, Sequence

from app.models.extracted_date import (
    ContractDateCandidate,
    ExtractedDate,
)


class ContractDateSelector:
    """
    Classifica datas extraídas conforme indícios textuais próximos.

    Este componente não afirma que uma data seja definitivamente a data
    de pactuação. Ele seleciona a candidata tecnicamente mais provável.
    """

    POSITIVE_TERMS: Final[dict[str, int]] = {
        "data da contratacao": 12,
        "data de contratacao": 12,
        "data da pactuacao": 12,
        "data de pactuacao": 12,
        "contratado em": 10,
        "contratacao realizada": 10,
        "assinado em": 9,
        "assinatura realizada": 9,
        "data da assinatura": 9,
        "data de assinatura": 9,
        "aceite realizado": 8,
        "data do aceite": 8,
        "formalizado em": 8,
        "celebrado em": 8,
        "firmado em": 8,
        "emitido em": 3,
        "gerado em": 3,
    }

    NEGATIVE_TERMS: Final[dict[str, int]] = {
        "data de nascimento": -15,
        "nascimento": -10,
        "data de emissao": -8,
        "data de expedicao": -8,
        "validade": -8,
        "vencimento": -8,
        "primeiro vencimento": -10,
        "ultima parcela": -8,
        "data de impressao": -5,
    }

    def __init__(self, minimum_score: int = 5) -> None:
        self.minimum_score = minimum_score

    def rank(
        self,
        dates: Sequence[ExtractedDate],
    ) -> list[ContractDateCandidate]:
        candidates = [
            self._evaluate(extracted_date)
            for extracted_date in dates
        ]

        return sorted(
            candidates,
            key=lambda candidate: (
                -candidate.score,
                candidate.extracted_date.start,
            ),
        )

    def select(
        self,
        dates: Sequence[ExtractedDate],
    ) -> ContractDateCandidate | None:
        ranked = self.rank(dates)

        if not ranked:
            return None

        selected = ranked[0]

        if selected.score < self.minimum_score:
            return None

        return selected

    def _evaluate(
        self,
        extracted_date: ExtractedDate,
    ) -> ContractDateCandidate:
        normalized_context = self._normalize_text(
            extracted_date.context
        )

        score = 0
        reasons: list[str] = []

        normalized_date = self._normalize_text(extracted_date.raw_text)
        date_matches = tuple(
            re.finditer(re.escape(normalized_date), normalized_context)
        )
        context_center = len(normalized_context) // 2
        date_center = min(
            (
                (match.start() + match.end()) // 2
                for match in date_matches
            ),
            key=lambda center: abs(center - context_center),
            default=context_center,
        )

        indicators: list[tuple[int, int, str, str]] = []

        for kind, terms in (
            ("positivo", self.POSITIVE_TERMS),
            ("negativo", self.NEGATIVE_TERMS),
        ):
            for term, weight in terms.items():
                distance = self._term_distance(
                    normalized_context, term, date_center
                )
                if distance is not None:
                    indicators.append((distance, weight, kind, term))

        if indicators:
            distance, weight, kind, term = min(
                indicators,
                key=lambda item: (item[0], -abs(item[1]), item[3]),
            )
            applied_weight = self._proximity_weight(weight, distance)
            score += applied_weight
            reasons.append(
                f"Indicador {kind} mais próximo: {term} ({applied_weight:+d})"
            )

        if extracted_date.has_four_digit_year:
            score += 1
            reasons.append("Ano apresentado com quatro dígitos")
        else:
            score -= 1
            reasons.append("Ano apresentado com dois dígitos")

        if not reasons:
            reasons.append(
                "Data válida, porém sem indicador contextual específico"
            )

        return ContractDateCandidate(
            extracted_date=extracted_date,
            score=score,
            reasons=tuple(reasons),
        )

    @staticmethod
    def _normalize_text(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value)

        without_accents = "".join(
            character
            for character in normalized
            if not unicodedata.combining(character)
        )

        without_accents = without_accents.lower()

        return re.sub(
            r"\s+",
            " ",
            without_accents,
        ).strip()

    @staticmethod
    def _term_distance(
        context: str,
        term: str,
        date_center: int,
    ) -> int | None:
        normalized_term = re.escape(term)
        matches = tuple(
            re.finditer(rf"\b{normalized_term}\b", context)
        )

        if not matches:
            return None

        return min(
            abs(((match.start() + match.end()) // 2) - date_center)
            + (
                20
                if ((match.start() + match.end()) // 2) > date_center
                else 0
            )
            for match in matches
        )

    @staticmethod
    def _proximity_weight(weight: int, distance: int) -> int:
        if distance <= 35:
            return weight
        if distance <= 70:
            return int(weight / 2)
        return 0

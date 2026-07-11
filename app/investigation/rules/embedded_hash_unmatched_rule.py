import re

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    info_badge,
    neutral_badge,
    warning_badge,
)


class EmbeddedHashUnmatchedRule(BaseCorrelationRule):
    """
    Identifica hashes presentes no conteúdo textual que não
    correspondem aos hashes dos arquivos analisados.
    """

    rule_id = "embedded_hash_unmatched"
    name = "Hash textual sem correspondência"

    HASH_PATTERN = re.compile(
        r"(?<![a-fA-F0-9])"
        r"("
        r"[a-fA-F0-9]{32}"
        r"|[a-fA-F0-9]{40}"
        r"|[a-fA-F0-9]{56}"
        r"|[a-fA-F0-9]{64}"
        r"|[a-fA-F0-9]{96}"
        r"|[a-fA-F0-9]{128}"
        r")"
        r"(?![a-fA-F0-9])"
    )

    ALGORITHM_BY_LENGTH = {
        32: "MD5",
        40: "SHA-1",
        56: "SHA-224",
        64: "SHA-256",
        96: "SHA-384",
        128: "SHA-512",
    }

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        calculated_hashes = self._all_calculated_hashes(
            context.calculated_hashes
        )

        for source_file, text in context.extracted_texts.items():
            embedded_hashes = self._extract_hashes(text)

            for embedded_hash in embedded_hashes:
                if embedded_hash in calculated_hashes:
                    continue

                algorithm = self.ALGORITHM_BY_LENGTH.get(
                    len(embedded_hash),
                    "Hash",
                )

                self.add_warning(
                    findings,
                    title="Hash sem correspondência",
                    description=(
                        f"O hash presente no corpo de {source_file} "
                        "não corresponde aos hashes calculados dos "
                        "arquivos analisados."
                    ),
                    icon="hash-warning",
                    source_file=source_file,
                    badges=[
                        info_badge(algorithm),
                        warning_badge("Sem correspondência"),
                        neutral_badge(source_file),
                    ],
                    metadata={
                        "arquivo_origem": source_file,
                        "algoritmo_provavel": algorithm,
                        "hash": embedded_hash,
                        "observacao": (
                            "O valor pode representar hash externo, "
                            "identificador interno ou UUID."
                        ),
                    },
                )

        return findings

    def _all_calculated_hashes(
        self,
        calculated_hashes: dict[str, dict[str, str]],
    ) -> set[str]:
        values: set[str] = set()

        for hashes in calculated_hashes.values():
            for hash_value in hashes.values():
                normalized_hash = self._normalize_hash(
                    hash_value
                )

                if normalized_hash:
                    values.add(normalized_hash)

        return values

    def _extract_hashes(
        self,
        text: str,
    ) -> set[str]:
        hashes: set[str] = set()

        for match in self.HASH_PATTERN.finditer(
            text or ""
        ):
            hashes.add(
                self._normalize_hash(
                    match.group(1)
                )
            )

        return hashes

    @staticmethod
    def _normalize_hash(
        value: str,
    ) -> str:
        return "".join(
            character
            for character in str(value).strip().lower()
            if character.isalnum()
        )
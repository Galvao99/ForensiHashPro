import re

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    info_badge,
    neutral_badge,
    success_badge,
)


class EmbeddedHashMatchRule(BaseCorrelationRule):
    """
    Correlaciona hashes presentes no corpo textual de um documento
    com os hashes calculados dos arquivos analisados.
    """

    rule_id = "embedded_hash_match"
    name = "Hash textual compatível com arquivo analisado"

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

        normalized_hashes = self._build_hash_lookup(
            context.calculated_hashes
        )

        for source_file, text in context.extracted_texts.items():
            embedded_hashes = self._extract_hashes(text)

            for embedded_hash in embedded_hashes:
                matches = normalized_hashes.get(
                    embedded_hash,
                    [],
                )

                for target_file, algorithm in matches:
                    if target_file == source_file:
                        continue

                    self.add_ok(
                        findings,
                        title="Hash correspondente entre arquivos",
                        description=(
                            f"O hash presente no corpo de {source_file} "
                            f"corresponde ao hash calculado de {target_file}."
                        ),
                        icon="hash",
                        source_file=source_file,
                        target_file=target_file,
                        badges=[
                            info_badge(algorithm),
                            success_badge("Correspondência"),
                            neutral_badge(source_file),
                            neutral_badge(target_file),
                        ],
                        metadata={
                            "arquivo_origem": source_file,
                            "arquivo_correspondente": target_file,
                            "algoritmo": algorithm,
                            "hash": embedded_hash,
                        },
                    )

        return findings

    def _build_hash_lookup(
        self,
        calculated_hashes: dict[str, dict[str, str]],
    ) -> dict[str, list[tuple[str, str]]]:
        lookup: dict[str, list[tuple[str, str]]] = {}

        for file_name, hashes in calculated_hashes.items():
            for algorithm, hash_value in hashes.items():
                normalized_hash = self._normalize_hash(
                    hash_value
                )

                if not normalized_hash:
                    continue

                lookup.setdefault(
                    normalized_hash,
                    [],
                ).append(
                    (
                        file_name,
                        self._format_algorithm(
                            algorithm
                        ),
                    )
                )

        return lookup

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

    @staticmethod
    def _format_algorithm(
        algorithm: str,
    ) -> str:
        normalized = str(
            algorithm
        ).strip().upper().replace(
            "_",
            "-",
        )

        aliases = {
            "SHA1": "SHA-1",
            "SHA224": "SHA-224",
            "SHA256": "SHA-256",
            "SHA384": "SHA-384",
            "SHA512": "SHA-512",
        }

        return aliases.get(
            normalized,
            normalized,
        )
import re

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class EmbeddedHashMatchRule(BaseCorrelationRule):
    rule_id = "embedded_hash_match"
    name = "Hash textual compatível com arquivo analisado"

    HASH_PATTERNS = {
        "MD5": r"\b[a-fA-F0-9]{32}\b",
        "SHA1": r"\b[a-fA-F0-9]{40}\b",
        "SHA256": r"\b[a-fA-F0-9]{64}\b",
        "SHA512": r"\b[a-fA-F0-9]{128}\b",
    }

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        calculated_lookup = self._build_hash_lookup(context)

        for source_file, text in context.extracted_texts.items():
            embedded_hashes = self._extract_hashes(text)

            for embedded_hash in embedded_hashes:
                normalized = embedded_hash.lower()
                matched = calculated_lookup.get(normalized)

                if not matched:
                    continue

                matched_file, algorithm = matched

                if matched_file == source_file:
                    continue

                findings.append(
                    CorrelationFinding(
                        title="Hash textual vinculado a outro arquivo",
                        message=(
                            f"Foi identificado no conteúdo do arquivo '{source_file}' "
                            f"um valor compatível com hash que corresponde ao {algorithm} "
                            f"calculado do arquivo '{matched_file}'. Esse achado sugere "
                            "vínculo técnico entre os documentos analisados."
                        ),
                        severity="info",
                        rule_id=self.rule_id,
                        related_files=[source_file, matched_file],
                        evidence={
                            "arquivo_origem": source_file,
                            "arquivo_correspondente": matched_file,
                            "algoritmo": algorithm,
                            "hash_identificado": embedded_hash,
                        },
                    )
                )

        return findings

    def _build_hash_lookup(
        self,
        context: InvestigationContext,
    ) -> dict[str, tuple[str, str]]:
        lookup: dict[str, tuple[str, str]] = {}

        for file_name, hashes in context.calculated_hashes.items():
            for algorithm, hash_value in hashes.items():
                lookup[hash_value.lower()] = (file_name, algorithm)

        return lookup

    def _extract_hashes(self, text: str) -> set[str]:
        found: set[str] = set()

        for pattern in self.HASH_PATTERNS.values():
            found.update(re.findall(pattern, text))

        return found
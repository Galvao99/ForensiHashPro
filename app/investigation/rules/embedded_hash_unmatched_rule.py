import re

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class EmbeddedHashUnmatchedRule(BaseCorrelationRule):
    rule_id = "embedded_hash_unmatched"
    name = "Hash textual sem correspondência"

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

        calculated_hashes = self._build_calculated_hash_set(context)

        for file_name, text in context.extracted_texts.items():
            embedded_hashes = self._extract_hashes(text)

            for embedded_hash in embedded_hashes:
                normalized = embedded_hash.lower()

                if normalized in calculated_hashes:
                    continue

                findings.append(
                    CorrelationFinding(
                        title="Valor textual com padrão de hash sem correspondência",
                        message=(
                            f"Foi identificado no conteúdo do arquivo '{file_name}' "
                            "um valor com padrão compatível com hash, porém sem correspondência "
                            "com os hashes calculados dos arquivos analisados. O valor pode "
                            "representar hash, UUID, identificador interno ou código institucional."
                        ),
                        severity="warning",
                        rule_id=self.rule_id,
                        related_files=[file_name],
                        evidence={
                            "arquivo": file_name,
                            "valor_identificado": embedded_hash,
                        },
                    )
                )

        return findings

    def _build_calculated_hash_set(
        self,
        context: InvestigationContext,
    ) -> set[str]:
        values: set[str] = set()

        for hashes in context.calculated_hashes.values():
            for hash_value in hashes.values():
                values.add(hash_value.lower())

        return values

    def _extract_hashes(self, text: str) -> set[str]:
        found: set[str] = set()

        for pattern in self.HASH_PATTERNS.values():
            found.update(re.findall(pattern, text))

        return found
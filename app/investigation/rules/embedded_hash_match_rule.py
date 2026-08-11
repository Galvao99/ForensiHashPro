from __future__ import annotations

from itertools import combinations
from pathlib import Path

from app.investigation.correlation_finding import CorrelationEvidence, CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class EmbeddedHashMatchRule(BaseCorrelationRule):
    rule_id = "embedded_hash_match"
    name = "Hash declarado correspondente"

    def evaluate(self, context: InvestigationContext) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []
        lookup = {
            value.lower(): (key, algorithm)
            for key, hashes in context.calculated_hashes.items()
            for algorithm, value in hashes.items()
        }
        for source_key, occurrences in context.declared_hashes.items():
            for occurrence in occurrences:
                if not occurrence.declared:
                    continue
                match = lookup.get(occurrence.value)
                if match is None or match[0] == source_key:
                    continue
                target_key, algorithm = match
                findings.append(CorrelationFinding(
                    title="Hash declarado correspondente",
                    description=(
                        f"Hash {algorithm} declarado em {occurrence.filename} corresponde "
                        f"ao conteúdo calculado de {context.display_name_for(target_key)}."
                    ),
                    severity="ok",
                    rule_id=self.rule_id,
                    category="embedded_hash_match",
                    source_file=source_key,
                    target_file=target_key,
                    evidence=[
                        CorrelationEvidence(
                            occurrence.evidence_ref, occurrence.filename,
                            source_type=occurrence.source_type, page=occurrence.page,
                            start=occurrence.start, end=occurrence.end,
                            field_path=occurrence.field_path, context=occurrence.context,
                            raw_value=occurrence.value, normalized_value=occurrence.value,
                            extractor=occurrence.extractor,
                        ),
                        CorrelationEvidence(
                            target_key, context.display_name_for(target_key),
                            role="calculated_hash", normalized_value=occurrence.value,
                            extractor="hash_engine",
                        ),
                    ],
                    confidence=1.0,
                    metadata={"algorithm": algorithm, "hash": occurrence.value},
                ))
        findings.extend(self._cross_file_matches(context))
        return findings

    def _cross_file_matches(self, context: InvestigationContext) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []
        for (left_key, left), (right_key, right) in combinations(
            context.calculated_hashes.items(), 2
        ):
            left_sha = left.get("SHA-256")
            right_sha = right.get("SHA-256")
            if not left_sha or left_sha.lower() != str(right_sha).lower():
                continue
            findings.append(CorrelationFinding(
                title="Conteúdo binário idêntico entre artefatos",
                description=(
                    f"Os artefatos {context.display_name_for(left_key)} e "
                    f"{context.display_name_for(right_key)} possuem o mesmo SHA-256 calculado."
                ),
                severity="info",
                rule_id="cross_file_match",
                category="cross_file_match",
                source_file=left_key,
                target_file=right_key,
                evidence=[
                    CorrelationEvidence(left_key, context.display_name_for(left_key), role="calculated_hash", normalized_value=left_sha, extractor="hash_engine"),
                    CorrelationEvidence(right_key, context.display_name_for(right_key), role="calculated_hash", normalized_value=left_sha, extractor="hash_engine"),
                ],
                confidence=1.0,
                metadata={"algorithm": "SHA-256", "hash": left_sha},
            ))
        return findings

    @staticmethod
    def artifact_matches_hint(hint: str, filename: str) -> bool:
        normalized_hint = "".join(ch.lower() for ch in hint if ch.isalnum())
        stem = "".join(ch.lower() for ch in Path(filename).stem if ch.isalnum())
        return bool(normalized_hint and stem and (stem in normalized_hint or normalized_hint in stem))

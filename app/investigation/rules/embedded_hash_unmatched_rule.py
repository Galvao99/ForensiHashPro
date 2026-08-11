from __future__ import annotations

from app.investigation.correlation_finding import CorrelationEvidence, CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.investigation.rules.embedded_hash_match_rule import EmbeddedHashMatchRule


class EmbeddedHashUnmatchedRule(BaseCorrelationRule):
    rule_id = "embedded_hash_unmatched"
    name = "Hash declarado sem correspondência"

    def evaluate(self, context: InvestigationContext) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []
        calculated = {
            str(value).lower()
            for hashes in context.calculated_hashes.values()
            for value in hashes.values()
        }
        for source_key, occurrences in context.declared_hashes.items():
            for occurrence in occurrences:
                if not occurrence.declared or occurrence.value in calculated:
                    continue
                mismatch_target = self._explicit_target(occurrence.artifact_hint, source_key, context)
                category = "declared_hash_mismatch" if mismatch_target else self.rule_id
                title = "Hash declarado divergente" if mismatch_target else "Hash declarado sem correspondência"
                description = (
                    f"O hash {occurrence.algorithm} explicitamente relacionado a "
                    f"{context.display_name_for(mismatch_target)} difere do hash calculado desse artefato."
                    if mismatch_target
                    else "Hash declarado no documento não possui artefato correspondente no conjunto analisado."
                )
                evidence = [CorrelationEvidence(
                    occurrence.evidence_ref, occurrence.filename,
                    source_type=occurrence.source_type, page=occurrence.page,
                    start=occurrence.start, end=occurrence.end,
                    field_path=occurrence.field_path, context=occurrence.context,
                    raw_value=occurrence.value, normalized_value=occurrence.value,
                    extractor=occurrence.extractor,
                )]
                target_file = None
                limitations = []
                if mismatch_target:
                    target_file = mismatch_target
                    calculated_value = context.calculated_hashes[mismatch_target].get(occurrence.algorithm)
                    evidence.append(CorrelationEvidence(
                        mismatch_target, context.display_name_for(mismatch_target),
                        role="calculated_hash", normalized_value=calculated_value,
                        extractor="hash_engine",
                    ))
                else:
                    limitations.append(
                        "O artefato correspondente pode simplesmente não integrar este Analysis Set."
                    )
                findings.append(CorrelationFinding(
                    title=title, description=description, severity="warning",
                    rule_id=category, category=category, source_file=source_key,
                    target_file=target_file, evidence=evidence,
                    confidence=1.0, limitations=limitations,
                    metadata={"algorithm": occurrence.algorithm, "hash": occurrence.value},
                ))
        return findings

    @staticmethod
    def _explicit_target(hint: str | None, source_key: str, context: InvestigationContext) -> str | None:
        if not hint:
            return None
        matches = [
            key for key in context.calculated_hashes
            if key != source_key
            and EmbeddedHashMatchRule.artifact_matches_hint(hint, context.display_name_for(key))
        ]
        return matches[0] if len(matches) == 1 else None

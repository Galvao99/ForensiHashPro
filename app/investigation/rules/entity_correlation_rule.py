from __future__ import annotations

from itertools import combinations

from app.entities import EntitySourceType, EntityType, NormalizedEntity
from app.investigation.correlation_finding import (
    CorrelationEntityRef,
    CorrelationEvidence,
    CorrelationFinding,
)
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.investigation.semantic_roles import comparable_role, semantic_role


SUPPORTED_TYPES = {
    EntityType.CPF,
    EntityType.PHONE,
    EntityType.IP,
    EntityType.MONEY,
    EntityType.DATETIME,
    EntityType.EMAIL,
}


class EntityCorrelationRule(BaseCorrelationRule):
    rule_id = "entity_correlation_v2"
    name = "Correlação de entidades normalizadas"

    def evaluate(self, context: InvestigationContext) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []
        items = [
            (key, entity, comparable_role(entity.entity_type, entity.sources))
            for key, entities in context.resolved_entities.items()
            for entity in entities
            if entity.entity_type in SUPPORTED_TYPES
        ]
        self._cross_file(items, context, findings)
        self._source_divergence(context, findings)
        return findings

    def _cross_file(self, items, context, findings) -> None:
        for (left_key, left, left_role), (right_key, right, right_role) in combinations(items, 2):
            if left_key == right_key or left.entity_type is not right.entity_type:
                continue
            if left_role is None or left_role != right_role:
                continue
            same = left.normalized_value == right.normalized_value
            category = "entity_match" if same else "entity_mismatch"
            severity = "info" if same else "warning"
            relation = "coincidente" if same else "divergente"
            findings.append(self._finding(
                category=category,
                severity=severity,
                title=f"{left.entity_type.value.upper()} {relation} entre arquivos",
                description=(
                    f"As entidades de tipo {left.entity_type.value} com papel semântico "
                    f"'{left_role}' possuem valores {'iguais' if same else 'diferentes'}."
                ),
                left_key=left_key,
                right_key=right_key,
                left=left,
                right=right,
                role=left_role,
                context=context,
            ))

    def _source_divergence(
        self, context: InvestigationContext, findings: list[CorrelationFinding]
    ) -> None:
        for evidence_key, entities in context.resolved_entities.items():
            typed = [entity for entity in entities if entity.entity_type in SUPPORTED_TYPES]
            for left, right in combinations(typed, 2):
                if left.entity_type is not right.entity_type:
                    continue
                left_role = comparable_role(left.entity_type, left.sources)
                right_role = comparable_role(right.entity_type, right.sources)
                if left_role is None or left_role != right_role:
                    continue
                if left.normalized_value == right.normalized_value:
                    continue
                if not self._native_ocr_pair(left, right):
                    continue
                findings.append(self._finding(
                    category="source_divergence",
                    severity="warning",
                    title=f"Divergência entre texto nativo e OCR ({left.entity_type.value})",
                    description=(
                        "Fontes textuais comparáveis da mesma evidência produziram "
                        "valores normalizados diferentes; nenhuma fonte foi escolhida como correta."
                    ),
                    left_key=evidence_key,
                    right_key=evidence_key,
                    left=left,
                    right=right,
                    role=left_role,
                    context=context,
                ))

    @staticmethod
    def _native_ocr_pair(left: NormalizedEntity, right: NormalizedEntity) -> bool:
        left_sources = {source.source_type for source in left.sources}
        right_sources = {source.source_type for source in right.sources}
        return (
            EntitySourceType.NATIVE_TEXT in left_sources
            and EntitySourceType.OCR in right_sources
        ) or (
            EntitySourceType.OCR in left_sources
            and EntitySourceType.NATIVE_TEXT in right_sources
        )

    def _finding(
        self, *, category: str, severity: str, title: str, description: str,
        left_key: str, right_key: str, left: NormalizedEntity,
        right: NormalizedEntity, role: str, context: InvestigationContext,
    ) -> CorrelationFinding:
        evidence = self._evidence(left_key, left, role, context) + self._evidence(
            right_key, right, role, context
        )
        return CorrelationFinding(
            title=title,
            description=description,
            severity=severity,
            rule_id=("source_divergence" if category == "source_divergence" else category),
            source_file=left_key,
            target_file=right_key if right_key != left_key else None,
            category=category,
            evidence=evidence,
            entities=[
                CorrelationEntityRef(left.entity_type.value, left.normalized_value, left.confidence, role),
                CorrelationEntityRef(right.entity_type.value, right.normalized_value, right.confidence, role),
            ],
            confidence=min(left.confidence, right.confidence),
            metadata={"semantic_role": role, "comparison_basis": "same_type_and_semantic_role"},
        )

    @staticmethod
    def _evidence(
        key: str, entity: NormalizedEntity, role: str, context: InvestigationContext
    ) -> list[CorrelationEvidence]:
        filename = context.display_name_for(key)
        return [
            CorrelationEvidence(
                evidence_ref=source.source_file,
                filename=filename,
                role=semantic_role(entity.entity_type, source) or role,
                source_type=source.source_type.value,
                page=source.page,
                start=source.start,
                end=source.end,
                field_path=source.field_path,
                context=source.context,
                raw_value=entity.raw_values[0] if entity.raw_values else None,
                normalized_value=entity.normalized_value,
                extractor=source.extractor,
            )
            for source in entity.sources
        ]

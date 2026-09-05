from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from app.correlation.v2.identity import stable_digest
from app.correlation.v2.models import (
    CorrelationCandidate, CorrelationEntity, CorrelationOccurrence,
    CorrelationRelation, CorrelationReport, CorrelationSummary,
    DerivedFromCandidate, EntityType, RelationType, SourceFileIdentity,
    StructuredRelationCandidate,
)
from app.correlation.v2.normalization import CorrelationNormalizer


@dataclass(frozen=True, slots=True)
class CorrelationLimits:
    max_occurrences: int = 100_000
    max_entities: int = 50_000
    max_context_length: int = 240

    def __post_init__(self) -> None:
        if min(self.max_occurrences, self.max_entities, self.max_context_length) < 1:
            raise ValueError("Correlation limits must be positive.")


class EvidenceGraphCorrelationEngine:
    """Builds a deterministic factual graph through indexed exact matches."""

    def __init__(
        self, normalizer: CorrelationNormalizer | None = None,
        limits: CorrelationLimits | None = None,
    ) -> None:
        self.normalizer = normalizer or CorrelationNormalizer()
        self.limits = limits or CorrelationLimits()

    def correlate(
        self, candidates: Iterable[CorrelationCandidate],
        *, derived_from: Iterable[DerivedFromCandidate] = (),
        structured_relations: Iterable[StructuredRelationCandidate] = (),
    ) -> CorrelationReport:
        derived_edges = tuple(derived_from)
        semantic_edges = tuple(structured_relations)
        indexed: dict[tuple[EntityType, str, str | None], dict[str, CorrelationOccurrence]] = defaultdict(dict)
        limitations: list[str] = []
        accepted = 0
        for candidate in candidates:
            if accepted >= self.limits.max_occurrences:
                limitations.append(f"Occurrence limit reached ({self.limits.max_occurrences}).")
                break
            normalized = self.normalizer.normalize(
                candidate.entity_type,
                candidate.normalization_value if candidate.normalization_value is not None else candidate.raw_value,
            )
            if normalized is None:
                continue
            qualifier = self._identity_qualifier(candidate)
            identity = [candidate.entity_type.value, normalized.value]
            if qualifier is not None:
                identity.extend([candidate.normalization_version, qualifier])
            entity_id = stable_digest("entity", identity)
            occurrence_payload = [
                entity_id, candidate.source_file.stable_id, candidate.provenance.identity_dict(),
            ]
            occurrence_id = stable_digest("occurrence", occurrence_payload)
            context = candidate.context
            if context is not None and len(context) > self.limits.max_context_length:
                context = context[: self.limits.max_context_length]
            occurrence = CorrelationOccurrence(
                occurrence_id=occurrence_id, entity_id=entity_id,
                entity_type=candidate.entity_type, raw_value=candidate.raw_value,
                normalized_value=normalized.value, source_file=candidate.source_file,
                provenance=candidate.provenance, context=context,
                semantic_role=candidate.semantic_role,
                normalization_version=candidate.normalization_version,
            )
            bucket = indexed[(candidate.entity_type, normalized.value, qualifier)]
            if occurrence_id not in bucket:
                bucket[occurrence_id] = occurrence
                accepted += 1
            elif self._preferred_occurrence(occurrence) < self._preferred_occurrence(bucket[occurrence_id]):
                bucket[occurrence_id] = occurrence

        ordered_keys = sorted(indexed, key=lambda key: (key[0].value, key[1], key[2] or ""))
        if len(ordered_keys) > self.limits.max_entities:
            ordered_keys = ordered_keys[: self.limits.max_entities]
            limitations.append(f"Entity limit reached ({self.limits.max_entities}).")

        entities: list[CorrelationEntity] = []
        files: dict[str, SourceFileIdentity] = {}
        for entity_type, normalized_value, qualifier in ordered_keys:
            occurrences = tuple(sorted(indexed[(entity_type, normalized_value, qualifier)].values(), key=self._occurrence_key))
            for occurrence in occurrences:
                files[occurrence.source_file.stable_id] = occurrence.source_file
            entities.append(CorrelationEntity(
                stable_id=occurrences[0].entity_id, entity_type=entity_type,
                normalized_value=normalized_value, display_value=occurrences[0].raw_value,
                occurrences=occurrences, occurrence_count=len(occurrences),
                unique_file_count=len({item.source_file.stable_id for item in occurrences}),
                unique_source_count=len({item.provenance.engine for item in occurrences}),
                semantic_role=occurrences[0].semantic_role,
                normalization_version=occurrences[0].normalization_version,
            ))

        for edge in derived_edges:
            files[edge.source_file.stable_id] = edge.source_file
            files[edge.derived_file.stable_id] = edge.derived_file
        relations = self._relations(entities, derived_edges, semantic_edges)
        counts: dict[str, int] = defaultdict(int)
        for entity in entities:
            counts[entity.entity_type.value] += 1
        summary = CorrelationSummary(
            total_entities=len(entities),
            total_occurrences=sum(item.occurrence_count for item in entities),
            total_relations=len(relations), entities_by_type=dict(sorted(counts.items())),
            cross_file_entities=sum(item.unique_file_count > 1 for item in entities),
            files_involved=len(files),
        )
        return CorrelationReport(tuple(entities), relations, summary, tuple(limitations))

    def _relations(
        self, entities: list[CorrelationEntity], derived_from: Iterable[DerivedFromCandidate],
        structured_relations: Iterable[StructuredRelationCandidate],
    ) -> tuple[CorrelationRelation, ...]:
        relations: dict[str, CorrelationRelation] = {}
        for entity in entities:
            file_ids = tuple(sorted({item.source_file.stable_id for item in entity.occurrences}))
            for file_id in file_ids:
                self._add_relation(relations, RelationType.ENTITY_OCCURS_IN_FILE, entity.stable_id, (file_id,), entity.stable_id)
            if len(file_ids) > 1:
                self._add_relation(relations, RelationType.SAME_ENTITY_ACROSS_FILES, entity.stable_id, file_ids, entity.stable_id)
                if entity.entity_type is EntityType.SHA256:
                    self._add_relation(relations, RelationType.SAME_HASH, entity.stable_id, file_ids, entity.stable_id)
        for item in derived_from:
            payload = [item.derived_file.stable_id, item.source_file.stable_id, item.provenance.to_dict()]
            relation_id = stable_digest(RelationType.DERIVED_FROM.value, payload)
            relations[relation_id] = CorrelationRelation(
                relation_id, RelationType.DERIVED_FROM, item.derived_file.stable_id,
                (item.source_file.stable_id,), provenance=item.provenance,
            )
        for item in structured_relations:
            object_ids = tuple(sorted(set(item.object_ids)))
            payload = [item.subject_id, object_ids, item.provenance.identity_dict()]
            relation_id = stable_digest(item.relation_type.value, payload)
            relations[relation_id] = CorrelationRelation(
                relation_id, item.relation_type, item.subject_id, object_ids,
                provenance=item.provenance,
            )
        return tuple(sorted(relations.values(), key=lambda item: (item.relation_type.value, item.subject_id, item.object_ids)))

    @staticmethod
    def _add_relation(
        relations: dict[str, CorrelationRelation], relation_type: RelationType,
        subject_id: str, object_ids: tuple[str, ...], entity_id: str | None,
    ) -> None:
        relation_id = stable_digest("relation", [relation_type.value, subject_id, object_ids, entity_id])
        relations[relation_id] = CorrelationRelation(
            relation_id, relation_type, subject_id, object_ids, entity_id=entity_id,
        )

    @staticmethod
    def _occurrence_key(item: CorrelationOccurrence) -> tuple[object, ...]:
        provenance = item.provenance
        return (
            item.source_file.stable_id, provenance.engine, provenance.field or "",
            provenance.path or "", provenance.page if provenance.page is not None else -1,
            provenance.offset_start if provenance.offset_start is not None else -1,
            provenance.start if provenance.start is not None else -1, item.occurrence_id,
        )

    @staticmethod
    def _preferred_occurrence(item: CorrelationOccurrence) -> tuple[object, ...]:
        return (
            item.provenance.derived_view is not None,
            item.raw_value,
            item.context or "",
            str(item.provenance.to_dict()),
        )

    @staticmethod
    def _identity_qualifier(candidate: CorrelationCandidate) -> str | None:
        """Keep V2 IDs for ordinary facts; separate roles that change hash meaning."""
        if candidate.entity_type in {EntityType.SHA256, EntityType.MD5}:
            if candidate.semantic_role in {"declared_hash", "hash_like"}:
                return candidate.semantic_role
        return None

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from app.correlation.v2.models import (
    CorrelationEntity,
    CorrelationOccurrence,
    CorrelationRelation,
    CorrelationReport,
    EntityType,
)


@dataclass(slots=True)
class CaseEvidenceIndex:
    """Canonical, UI-independent lookup index over one evidence graph."""

    report: CorrelationReport
    _facts_by_id: dict[str, CorrelationEntity] = field(init=False, default_factory=dict)
    _occurrences_by_id: dict[str, CorrelationOccurrence] = field(init=False, default_factory=dict)
    _by_value: dict[tuple[EntityType, str], list[CorrelationOccurrence]] = field(init=False, default_factory=dict)
    _by_artifact: dict[str, list[CorrelationOccurrence]] = field(init=False, default_factory=dict)
    _by_type: dict[EntityType, list[CorrelationOccurrence]] = field(init=False, default_factory=dict)
    _by_source_type: dict[str, list[CorrelationOccurrence]] = field(init=False, default_factory=dict)
    _by_role: dict[str, list[CorrelationOccurrence]] = field(init=False, default_factory=dict)
    _relations_by_id: dict[str, CorrelationRelation] = field(init=False, default_factory=dict)

    def __post_init__(self) -> None:
        by_value: dict[tuple[EntityType, str], list[CorrelationOccurrence]] = defaultdict(list)
        by_artifact: dict[str, list[CorrelationOccurrence]] = defaultdict(list)
        by_type: dict[EntityType, list[CorrelationOccurrence]] = defaultdict(list)
        by_source: dict[str, list[CorrelationOccurrence]] = defaultdict(list)
        by_role: dict[str, list[CorrelationOccurrence]] = defaultdict(list)
        for fact in self.report.entities:
            self._facts_by_id[fact.stable_id] = fact
            for occurrence in fact.occurrences:
                self._occurrences_by_id[occurrence.occurrence_id] = occurrence
                by_value[(fact.entity_type, fact.normalized_value)].append(occurrence)
                by_artifact[occurrence.source_file.stable_id].append(occurrence)
                by_type[fact.entity_type].append(occurrence)
                source_type = occurrence.provenance.source_type or occurrence.provenance.engine
                by_source[source_type].append(occurrence)
                if occurrence.semantic_role:
                    by_role[occurrence.semantic_role].append(occurrence)
        self._by_value = self._frozen_lists(by_value)
        self._by_artifact = self._frozen_lists(by_artifact)
        self._by_type = self._frozen_lists(by_type)
        self._by_source_type = self._frozen_lists(by_source)
        self._by_role = self._frozen_lists(by_role)
        self._relations_by_id = {item.stable_id: item for item in self.report.relations}

    @staticmethod
    def _frozen_lists(values: dict[object, list[CorrelationOccurrence]]) -> dict:
        return {
            key: list(sorted(items, key=lambda item: item.occurrence_id))
            for key, items in values.items()
        }

    def fact(self, fact_id: str) -> CorrelationEntity | None:
        return self._facts_by_id.get(fact_id)

    def occurrence(self, occurrence_id: str) -> CorrelationOccurrence | None:
        return self._occurrences_by_id.get(occurrence_id)

    def relation(self, relation_id: str) -> CorrelationRelation | None:
        return self._relations_by_id.get(relation_id)

    def find(self, fact_type: EntityType, normalized_value: str) -> tuple[CorrelationOccurrence, ...]:
        return tuple(self._by_value.get((fact_type, normalized_value), ()))

    def for_artifact(self, artifact_id: str) -> tuple[CorrelationOccurrence, ...]:
        return tuple(self._by_artifact.get(artifact_id, ()))

    def by_type(self, fact_type: EntityType) -> tuple[CorrelationOccurrence, ...]:
        return tuple(self._by_type.get(fact_type, ()))

    def by_source_type(self, source_type: str) -> tuple[CorrelationOccurrence, ...]:
        return tuple(self._by_source_type.get(source_type, ()))

    def by_semantic_role(self, role: str) -> tuple[CorrelationOccurrence, ...]:
        return tuple(self._by_role.get(role, ()))

    def trace_occurrences(self, occurrence_ids: Iterable[str]) -> tuple[CorrelationOccurrence, ...]:
        return tuple(
            item for key in sorted(set(occurrence_ids))
            if (item := self._occurrences_by_id.get(key)) is not None
        )

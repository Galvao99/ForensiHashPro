from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from app.correlation.case_result import (
    CaseFinding, CaseResult, EpistemicState, RuleExecutionLimitation,
)
from app.correlation.v2.engine import EvidenceGraphCorrelationEngine
from app.correlation.v2.index import CaseEvidenceIndex
from app.correlation.v2.models import CorrelationReport, EntityType, RelationType
from app.correlation.v2.providers import AnalysisResultCorrelationProvider
from app.enum.severity import Severity
from app.models import AnalysisResult
from app.processing import ProcessingStatus


class DeterministicCaseRule(Protocol):
    rule_id: str
    rule_version: str
    required_fact_types: frozenset[EntityType]

    def evaluate(self, index: CaseEvidenceIndex) -> tuple[CaseFinding, ...]: ...


class IdenticalCalculatedHashRule:
    rule_id = "case.identical_calculated_hash"
    rule_version = "1"
    required_fact_types = frozenset({EntityType.SHA256})

    def evaluate(self, index: CaseEvidenceIndex) -> tuple[CaseFinding, ...]:
        findings: list[CaseFinding] = []
        for fact in index.report.entities:
            if fact.entity_type is not EntityType.SHA256:
                continue
            supports = tuple(
                item.occurrence_id for item in fact.occurrences
                if item.semantic_role == "calculated_hash"
            )
            artifacts = {
                item.source_file.stable_id for item in fact.occurrences
                if item.semantic_role == "calculated_hash"
            }
            if len(artifacts) < 2:
                continue
            relation = next(
                (item for item in index.report.relations
                 if item.relation_type is RelationType.SAME_HASH and item.entity_id == fact.stable_id),
                None,
            )
            findings.append(CaseFinding(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                epistemic_state=EpistemicState.MATCH,
                severity=Severity.INFO,
                title="Conteúdo binário idêntico entre artefatos",
                statement="Artefatos distintos possuem o mesmo SHA-256 calculado a partir de seus bytes.",
                supporting_occurrence_ids=supports,
                relation_id=relation.stable_id if relation else None,
                metadata={"fact_id": fact.stable_id, "algorithm": "SHA-256"},
            ))
        return tuple(findings)


@dataclass(frozen=True, slots=True)
class CanonicalCasePipelineResult:
    graph: CorrelationReport
    index: CaseEvidenceIndex
    case_result: CaseResult


class CanonicalCasePipeline:
    """Parser outputs -> canonical graph/index -> deterministic rules."""

    def __init__(
        self,
        *,
        provider: AnalysisResultCorrelationProvider | None = None,
        graph_engine: EvidenceGraphCorrelationEngine | None = None,
        rules: Sequence[DeterministicCaseRule] | None = None,
    ) -> None:
        self.provider = provider or AnalysisResultCorrelationProvider()
        self.graph_engine = graph_engine or EvidenceGraphCorrelationEngine()
        self.rules = tuple(rules) if rules is not None else (IdenticalCalculatedHashRule(),)

    def analyze(self, case_id: str, results: Sequence[AnalysisResult]) -> CanonicalCasePipelineResult:
        graph = self.graph_engine.correlate(self.provider.provide_many(results))
        index = CaseEvidenceIndex(graph)
        findings: list[CaseFinding] = []
        limitations: list[RuleExecutionLimitation] = []
        for rule in self.rules:
            try:
                findings.extend(rule.evaluate(index))
            except Exception as error:
                limitations.append(RuleExecutionLimitation(
                    rule_id=rule.rule_id,
                    rule_version=rule.rule_version,
                    code="rule_execution_failed",
                    status=ProcessingStatus.FAILED,
                    message="A regra não pôde ser concluída; fatos válidos foram preservados.",
                    metadata={"error_type": type(error).__name__},
                ))
        return CanonicalCasePipelineResult(
            graph, index,
            CaseResult(case_id, findings=tuple(findings), limitations=tuple(limitations)),
        )

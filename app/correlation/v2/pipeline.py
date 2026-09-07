from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol, Sequence

from app.correlation.case_result import (
    CaseFinding, CaseResult, EpistemicState, RuleExecutionLimitation,
)
from app.correlation.v2.engine import EvidenceGraphCorrelationEngine
from app.correlation.v2.identity import stable_digest
from app.correlation.v2.index import CaseEvidenceIndex
from app.correlation.v2.models import (
    CorrelationOccurrence, CorrelationRelation, CorrelationReport,
    EntityType, RelationType,
)
from app.correlation.v2.providers import AnalysisResultCorrelationProvider
from app.enum.severity import Severity
from app.models import AnalysisResult
from app.processing import ProcessingStatus
from app.services.temporal_parser import TemporalInterval, TemporalParser


class DeterministicCaseRule(Protocol):
    rule_id: str
    rule_version: str
    required_fact_types: frozenset[EntityType]

    def evaluate(
        self, index: CaseEvidenceIndex,
    ) -> tuple[CaseFinding, ...] | "DeterministicRuleResult": ...


@dataclass(frozen=True, slots=True)
class DeterministicRuleResult:
    findings: tuple[CaseFinding, ...] = ()
    limitations: tuple[RuleExecutionLimitation, ...] = ()


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


class DeclaredHashVerificationRule:
    """Compare only declarations explicitly bound upstream to one artifact."""

    rule_id = "case.declared_hash_verification"
    rule_version = "1"
    required_fact_types = frozenset({EntityType.SHA256, EntityType.MD5})

    def evaluate(self, index: CaseEvidenceIndex) -> tuple[CaseFinding, ...]:
        findings: list[CaseFinding] = []
        for binding in index.relations_by_type(RelationType.DECLARED_HASH_TARGET):
            if len(binding.object_ids) != 1:
                continue
            declared = index.occurrence(binding.subject_id)
            if declared is None or declared.semantic_role != "declared_hash":
                continue
            target_id = binding.object_ids[0]
            calculated = tuple(
                item for item in index.for_artifact(target_id)
                if item.semantic_role == "calculated_hash"
                and item.entity_type is declared.entity_type
            )
            if len(calculated) != 1:
                continue
            calculated_occurrence = calculated[0]
            state = (
                EpistemicState.MATCH
                if declared.normalized_value == calculated_occurrence.normalized_value
                else EpistemicState.MISMATCH
            )
            algorithm = _algorithm_label(declared.entity_type)
            findings.append(CaseFinding(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                epistemic_state=state,
                severity=Severity.INFO,
                title=(
                    "Hash declarado corresponde ao hash calculado"
                    if state is EpistemicState.MATCH
                    else "Hash declarado difere do hash calculado"
                ),
                statement=(
                    f"A declaração de {algorithm} vinculada ao artefato-alvo "
                    f"{'corresponde ao' if state is EpistemicState.MATCH else 'difere do'} "
                    "digest calculado pelo ForensiHash para esse artefato."
                ),
                supporting_occurrence_ids=(
                    declared.occurrence_id, calculated_occurrence.occurrence_id,
                ),
                relation_id=binding.stable_id,
                metadata={
                    "algorithm": algorithm,
                    "declared_fact_id": declared.entity_id,
                    "calculated_fact_id": calculated_occurrence.entity_id,
                    "source_artifact_id": declared.source_file.stable_id,
                    "target_artifact_id": target_id,
                },
            ))
        return tuple(sorted(findings, key=lambda item: item.finding_id))


class SigningTimeCertificateValidityRule:
    """Verify temporal containment, not signature or certificate validity."""

    rule_id = "case.signing_time_certificate_validity"
    rule_version = "1"
    required_fact_types = frozenset({EntityType.TIMESTAMP})
    _COMPARABLE_PRECISIONS = frozenset(
        {"minute", "second", "millisecond", "microsecond"}
    )

    def evaluate(self, index: CaseEvidenceIndex) -> DeterministicRuleResult:
        findings: list[CaseFinding] = []
        limitations: list[RuleExecutionLimitation] = []
        signing_by_signature = _relations_by_subject(
            index.relations_by_type(RelationType.SIGNATURE_HAS_SIGNING_TIME)
        )
        certificate_by_signature = _relations_by_subject(
            index.relations_by_type(RelationType.SIGNATURE_USES_CERTIFICATE)
        )
        interval_by_certificate = _relations_by_subject(
            index.relations_by_type(RelationType.CERTIFICATE_VALIDITY_INTERVAL)
        )
        for signature_id in sorted(certificate_by_signature):
            certificate_relations = certificate_by_signature[signature_id]
            signing_relations = signing_by_signature.get(signature_id, ())
            if len(certificate_relations) != 1 or len(signing_relations) != 1:
                continue
            certificate_relation = certificate_relations[0]
            if len(certificate_relation.object_ids) != 1:
                continue
            certificate_id = certificate_relation.object_ids[0]
            intervals = interval_by_certificate.get(certificate_id, ())
            if len(intervals) != 1 or len(intervals[0].object_ids) != 2:
                continue
            signing = _single_occurrence(index, signing_relations[0].object_ids)
            bounds = tuple(
                item for occurrence_id in intervals[0].object_ids
                if (item := index.occurrence(occurrence_id)) is not None
            )
            if signing is None or len(bounds) != 2:
                continue
            not_before = next(
                (item for item in bounds if item.semantic_role == "certificate_not_before"),
                None,
            )
            not_after = next(
                (item for item in bounds if item.semantic_role == "certificate_not_after"),
                None,
            )
            if (
                signing.semantic_role != "signer_declared_signing_time"
                or not_before is None or not_after is None
            ):
                continue
            occurrences = (signing, not_before, not_after)
            if any(
                item.provenance.timestamp_precision not in self._COMPARABLE_PRECISIONS
                for item in occurrences
            ):
                continue
            parsed = tuple(_temporal_value(item.normalized_value) for item in occurrences)
            if any(item is None for item in parsed):
                continue
            signing_time, lower, upper = (item for item in parsed if item is not None)
            awareness = {item.utcoffset() is not None for item in (signing_time, lower, upper)}
            if len(awareness) != 1:
                continue
            comparable = tuple(_utc_if_aware(item) for item in (signing_time, lower, upper))
            signing_value, lower_value, upper_value = comparable
            if upper_value < lower_value:
                limitations.append(RuleExecutionLimitation(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    code="malformed_certificate_validity_interval",
                    status=ProcessingStatus.PARTIAL,
                    message="Certificate NotAfter precedes NotBefore; temporal containment was not evaluated.",
                    metadata={
                        "signature_id": signature_id,
                        "certificate_id": certificate_id,
                        "interval_relation_id": intervals[0].stable_id,
                    },
                ))
                continue
            inside = lower_value <= signing_value <= upper_value
            state = EpistemicState.MATCH if inside else EpistemicState.MISMATCH
            position = (
                "inside" if inside else "before"
                if signing_value < lower_value else "after"
            )
            delta_seconds = (
                0.0 if inside else (lower_value - signing_value).total_seconds()
                if position == "before" else (signing_value - upper_value).total_seconds()
            )
            findings.append(CaseFinding(
                rule_id=self.rule_id,
                rule_version=self.rule_version,
                epistemic_state=state,
                severity=Severity.INFO,
                title=(
                    "SigningTime dentro do intervalo do certificado"
                    if inside else "SigningTime fora do intervalo do certificado"
                ),
                statement=(
                    "O SigningTime observado está dentro do intervalo NotBefore/NotAfter "
                    "declarado pelo certificado associado."
                    if inside else
                    "O SigningTime observado está fora do intervalo NotBefore/NotAfter "
                    "declarado pelo certificado associado."
                ),
                supporting_occurrence_ids=tuple(
                    item.occurrence_id for item in occurrences
                ),
                relation_id=certificate_relation.stable_id,
                metadata={
                    "signature_id": signature_id,
                    "certificate_id": certificate_id,
                    "position": position,
                    "delta_seconds": delta_seconds,
                    "signing_time_relation_id": signing_relations[0].stable_id,
                    "certificate_interval_relation_id": intervals[0].stable_id,
                },
            ))
        return DeterministicRuleResult(
            tuple(sorted(findings, key=lambda item: item.finding_id)),
            tuple(sorted(limitations, key=lambda item: item.limitation_id)),
        )


class DocumentDateMetadataTemporalRule:
    """Describe a supported same-artifact temporal relation without inference."""

    rule_id = "case.document_date_metadata_temporal_relation"
    rule_version = "1"
    required_fact_types = frozenset({EntityType.TIMESTAMP})
    document_role = "document_date"
    metadata_roles = frozenset({
        "pdf_creation_date",
        "pdf_modify_date",
        "xmp_create_date",
        "xmp_modify_date",
        "xmp_metadata_date",
        # Compatibility for legacy ungrouped ExifTool projections.  The exact
        # field remains in provenance and is never relabelled as PDF or XMP.
        "metadata_creation_date",
        "metadata_modify_date",
        "metadata_date",
    })

    def __init__(self, parser: TemporalParser | None = None) -> None:
        self.parser = parser or TemporalParser()

    def evaluate(self, index: CaseEvidenceIndex) -> tuple[CaseFinding, ...]:
        documents_by_artifact = _occurrences_by_artifact(
            index.by_semantic_role(self.document_role)
        )
        metadata_by_artifact: dict[str, list[CorrelationOccurrence]] = {}
        for role in sorted(self.metadata_roles):
            for occurrence in index.by_semantic_role(role):
                metadata_by_artifact.setdefault(
                    occurrence.source_file.stable_id, []
                ).append(occurrence)

        findings: list[CaseFinding] = []
        for artifact_id in sorted(set(documents_by_artifact) & set(metadata_by_artifact)):
            document_occurrences = documents_by_artifact[artifact_id]
            # Ambiguity is normal absence of a conclusion, not a rule failure.
            if len(document_occurrences) != 1:
                continue
            document = document_occurrences[0]
            for metadata in sorted(
                metadata_by_artifact[artifact_id], key=lambda item: item.occurrence_id,
            ):
                relation = self._relation(document, metadata)
                if relation is None:
                    continue
                relation_type = relation
                metadata_field = (
                    metadata.provenance.metadata_key
                    or metadata.provenance.field
                    or metadata.semantic_role
                    or "metadata"
                )
                relation_id = stable_digest(
                    "document-date-metadata-relation-v1",
                    [
                        self.rule_id,
                        self.rule_version,
                        artifact_id,
                        document.occurrence_id,
                        metadata.occurrence_id,
                        metadata.semantic_role,
                        relation_type,
                    ],
                )
                findings.append(CaseFinding(
                    rule_id=self.rule_id,
                    rule_version=self.rule_version,
                    epistemic_state=EpistemicState.OBSERVED,
                    severity=Severity.INFO,
                    title=f"Data documental × {metadata_field}",
                    statement=_document_metadata_statement(
                        str(metadata_field), relation_type,
                    ),
                    supporting_occurrence_ids=(
                        document.occurrence_id, metadata.occurrence_id,
                    ),
                    relation_id=relation_id,
                    metadata={
                        "artifact_id": artifact_id,
                        "document_fact_id": document.entity_id,
                        "metadata_fact_id": metadata.entity_id,
                        "document_occurrence_id": document.occurrence_id,
                        "metadata_occurrence_id": metadata.occurrence_id,
                        "document_role": document.semantic_role,
                        "metadata_role": metadata.semantic_role,
                        "metadata_field": metadata_field,
                        "document_raw_value": document.raw_value,
                        "metadata_raw_value": metadata.raw_value,
                        "document_normalized_value": document.normalized_value,
                        "metadata_normalized_value": metadata.normalized_value,
                        "document_precision": document.provenance.timestamp_precision,
                        "metadata_precision": metadata.provenance.timestamp_precision,
                        "document_timezone_status": document.provenance.timezone_status,
                        "metadata_timezone_status": metadata.provenance.timezone_status,
                        "relation_type": relation_type,
                    },
                ))
        return tuple(sorted(findings, key=lambda item: item.finding_id))

    def _relation(
        self,
        document: CorrelationOccurrence,
        metadata: CorrelationOccurrence,
    ) -> str | None:
        if (
            not document.provenance.timestamp_precision
            or not metadata.provenance.timestamp_precision
            or not document.provenance.timezone_status
            or not metadata.provenance.timezone_status
        ):
            return None
        document_parsed = self.parser.parse(document.normalized_value)
        metadata_parsed = self.parser.parse(metadata.normalized_value)
        if document_parsed is None or metadata_parsed is None:
            return None
        if (
            document_parsed.precision != document.provenance.timestamp_precision
            or metadata_parsed.precision != metadata.provenance.timestamp_precision
            or document_parsed.timezone_status != document.provenance.timezone_status
            or metadata_parsed.timezone_status != metadata.provenance.timezone_status
        ):
            return None
        document_interval = self.parser.interval(document_parsed)
        metadata_interval = self.parser.interval(metadata_parsed)
        if document_interval is None or metadata_interval is None:
            return None
        return _compare_temporal_intervals(document_interval, metadata_interval)


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
        self.rules = tuple(rules) if rules is not None else (
            IdenticalCalculatedHashRule(), DeclaredHashVerificationRule(),
            SigningTimeCertificateValidityRule(),
            DocumentDateMetadataTemporalRule(),
        )

    def analyze(self, case_id: str, results: Sequence[AnalysisResult]) -> CanonicalCasePipelineResult:
        batch = self.provider.provide_case(results)
        graph = self.graph_engine.correlate(
            batch.candidates, declared_hash_targets=batch.declared_hash_targets,
            signature_temporal_bindings=batch.signature_temporal_bindings,
        )
        index = CaseEvidenceIndex(graph)
        findings: list[CaseFinding] = []
        limitations: list[RuleExecutionLimitation] = []
        for rule in self.rules:
            try:
                evaluated = rule.evaluate(index)
                if isinstance(evaluated, DeterministicRuleResult):
                    findings.extend(evaluated.findings)
                    limitations.extend(evaluated.limitations)
                else:
                    findings.extend(evaluated)
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


def _algorithm_label(entity_type: EntityType) -> str:
    return {EntityType.SHA256: "SHA-256", EntityType.MD5: "MD5"}[entity_type]


def _relations_by_subject(
    relations: Sequence[CorrelationRelation],
) -> dict[str, tuple[CorrelationRelation, ...]]:
    grouped: dict[str, list[CorrelationRelation]] = {}
    for relation in relations:
        grouped.setdefault(relation.subject_id, []).append(relation)
    return {
        key: tuple(sorted(values, key=lambda item: item.stable_id))
        for key, values in grouped.items()
    }


def _single_occurrence(
    index: CaseEvidenceIndex, occurrence_ids: tuple[str, ...],
) -> CorrelationOccurrence | None:
    if len(occurrence_ids) != 1:
        return None
    return index.occurrence(occurrence_ids[0])


def _temporal_value(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _utc_if_aware(value: datetime) -> datetime:
    return value.astimezone(timezone.utc) if value.utcoffset() is not None else value


def _occurrences_by_artifact(
    occurrences: Sequence[CorrelationOccurrence],
) -> dict[str, tuple[CorrelationOccurrence, ...]]:
    grouped: dict[str, list[CorrelationOccurrence]] = {}
    for occurrence in occurrences:
        grouped.setdefault(occurrence.source_file.stable_id, []).append(occurrence)
    return {
        artifact_id: tuple(sorted(values, key=lambda item: item.occurrence_id))
        for artifact_id, values in grouped.items()
    }


def _compare_temporal_intervals(
    document: TemporalInterval,
    metadata: TemporalInterval,
) -> str | None:
    document_aware = document.start.utcoffset() is not None
    metadata_aware = metadata.start.utcoffset() is not None
    if document_aware != metadata_aware:
        return None
    document_start = _utc_if_aware(document.start)
    document_end = _utc_if_aware(document.end)
    metadata_start = _utc_if_aware(metadata.start)
    metadata_end = _utc_if_aware(metadata.end)
    if document_end <= metadata_start:
        return "document_date_before_metadata"
    if metadata_end <= document_start:
        return "document_date_after_metadata"
    return "temporal_overlap"


def _document_metadata_statement(metadata_field: str, relation: str) -> str:
    if relation == "document_date_before_metadata":
        return (
            f"O valor temporal registrado no campo {metadata_field} é posterior ao "
            "intervalo representado pela data documental observada no mesmo artefato."
        )
    if relation == "document_date_after_metadata":
        return (
            f"O valor temporal registrado no campo {metadata_field} é anterior ao "
            "intervalo representado pela data documental observada no mesmo artefato."
        )
    return (
        f"O intervalo temporal registrado no campo {metadata_field} se sobrepõe ao "
        "intervalo representado pela data documental observada no mesmo artefato."
    )

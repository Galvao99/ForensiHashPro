from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from app.contracts import AnalysisContract, Fact
from app.entities import (
    ConfidenceComponent,
    EntityHypothesis,
    EntitySource,
    EntitySourceType,
    EntityType,
    NormalizedEntity,
)
from app.investigation.correlation_engine import CorrelationEngine
from app.investigation.correlation_result import CorrelationResult
from app.investigation.declared_hash import DeclaredHashExtractor
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.embedded_hash_match_rule import EmbeddedHashMatchRule
from app.investigation.rules.embedded_hash_unmatched_rule import EmbeddedHashUnmatchedRule
from app.investigation.rules.entity_correlation_rule import EntityCorrelationRule


@dataclass(frozen=True, slots=True)
class AnalysisSetArtifact:
    job_id: str
    state: str
    analysis_id: str | None = None
    evidence_ref: str | None = None
    filename: str = ""
    contract: AnalysisContract | None = None
    limitation: str | None = None


@dataclass(slots=True)
class AnalysisSetResult:
    set_id: str
    state: str
    artifacts: list[AnalysisSetArtifact]
    correlation_result: CorrelationResult
    created_at: datetime
    finished_at: datetime
    limitations: list[str] = field(default_factory=list)
    timeline_result: dict[str, object] = field(default_factory=dict)


class AnalysisSetCorrelator:
    """Correlação leve sobre contratos concluídos; não acessa arquivos."""

    def __init__(self, hash_extractor: DeclaredHashExtractor | None = None) -> None:
        self.hash_extractor = hash_extractor or DeclaredHashExtractor()
        self.engine = CorrelationEngine([
            EntityCorrelationRule(),
            EmbeddedHashMatchRule(),
            EmbeddedHashUnmatchedRule(),
        ])

    def correlate(
        self, set_id: str, artifacts: list[AnalysisSetArtifact],
        *, created_at: datetime | None = None,
    ) -> AnalysisSetResult:
        started = created_at or datetime.now(timezone.utc)
        context = InvestigationContext()
        limitations = [item.limitation for item in artifacts if item.limitation]
        for artifact in artifacts:
            if artifact.contract is not None:
                self._add_contract(context, artifact.contract)
        correlations = self.engine.evaluate(context)
        timeline_result = self._timeline_result(set_id, artifacts)
        successful = sum(item.contract is not None for item in artifacts)
        state = "completed" if successful == len(artifacts) else ("partial" if successful else "failed")
        return AnalysisSetResult(
            set_id=set_id,
            state=state,
            artifacts=artifacts,
            correlation_result=correlations,
            created_at=started,
            finished_at=datetime.now(timezone.utc),
            limitations=[str(item) for item in limitations],
            timeline_result=timeline_result,
        )

    @staticmethod
    def _timeline_result(
        set_id: str, artifacts: list[AnalysisSetArtifact]
    ) -> dict[str, object]:
        events: list[dict[str, object]] = []
        warnings: list[dict[str, object]] = []
        limitations: list[str] = []
        for artifact in artifacts:
            if artifact.contract is None:
                limitations.append(
                    artifact.limitation
                    or f"O artefato {artifact.filename} não possui Timeline disponível."
                )
                continue
            for record in artifact.contract.timeline or []:
                if not isinstance(record, dict):
                    continue
                safe = dict(record)
                safe["evidence_ref"] = artifact.evidence_ref
                safe["filename"] = artifact.filename
                if safe.get("record_type") == "warning":
                    warnings.append(safe)
                elif safe.get("record_type") == "limitation":
                    if safe.get("message"):
                        limitations.append(str(safe["message"]))
                else:
                    events.append(safe)
        events.sort(key=lambda item: (
            item.get("temporal_status") == "structural_only",
            str(item.get("timestamp") or ""),
            int(item.get("structural_sequence") or 0),
        ))
        return {
            "set_id": set_id,
            "events": events,
            "temporal_events": [item for item in events if item.get("temporal_status") != "structural_only"],
            "structural_events": [item for item in events if item.get("temporal_status") == "structural_only"],
            "warnings": warnings,
            "limitations": limitations,
            "summary": {
                "events": len(events),
                "temporal_events": sum(item.get("temporal_status") != "structural_only" for item in events),
                "structural_events": sum(item.get("temporal_status") == "structural_only" for item in events),
                "warnings": len(warnings),
            },
        }

    def _add_contract(self, context: InvestigationContext, contract: AnalysisContract) -> None:
        key = contract.evidence_id
        filename = str(contract.file.get("name") or "Evidência")
        context.display_names[key] = filename
        context.calculated_hashes[key] = {
            self._algorithm(key_name): str(value).lower()
            for key_name, value in contract.hashes.items()
            if value
        }
        entities = [entity for fact in contract.facts if (entity := self._entity(fact))]
        if entities:
            context.resolved_entities[key] = entities
        declared = []
        for source_type, section in (("native_text", contract.native_text), ("ocr", contract.ocr)):
            if not isinstance(section, dict):
                continue
            segments = section.get("segments")
            if isinstance(segments, list) and segments:
                for segment in segments:
                    if not isinstance(segment, dict):
                        continue
                    declared.extend(self.hash_extractor.extract_text(
                        str(segment.get("text") or ""), evidence_ref=key,
                        filename=filename, source_type=str(segment.get("source") or source_type),
                        page=segment.get("page"),
                    ))
            else:
                text = str(section.get("text") or "")
                declared.extend(self.hash_extractor.extract_text(
                    text, evidence_ref=key, filename=filename, source_type=source_type
                ))
        json_data = contract.technical_structure.get("json")
        if isinstance(json_data, dict):
            for item in json_data.get("fields", []) or []:
                if isinstance(item, dict):
                    declared.extend(self.hash_extractor.extract_json_field(
                        item.get("value"), evidence_ref=key, filename=filename,
                        field_path=str(item.get("path") or item.get("key") or "json"),
                    ))
        if declared:
            context.declared_hashes[key] = declared

    @staticmethod
    def _algorithm(value: str) -> str:
        compact = value.upper().replace("_", "-")
        return {
            "SHA1": "SHA-1", "SHA224": "SHA-224", "SHA256": "SHA-256",
            "SHA384": "SHA-384", "SHA512": "SHA-512",
        }.get(compact, compact)

    @staticmethod
    def _entity(fact: Fact) -> NormalizedEntity | None:
        if fact.kind != "entity" or fact.source != "entity_resolver_v2":
            return None
        data = fact.data
        try:
            entity_type = EntityType(str(data["type"]))
            sources = tuple(
                EntitySource(
                    source_type=EntitySourceType(str(item["source_type"])),
                    source_file=str(item["evidence_ref"]),
                    page=item.get("page"), start=item.get("start"), end=item.get("end"),
                    context_before=str(item.get("context_before") or ""),
                    context_after=str(item.get("context_after") or ""),
                    extractor=str(item.get("extractor") or "entity_resolver_v2"),
                    field_path=item.get("field_path"),
                )
                for item in data.get("provenance", [])
                if isinstance(item, dict)
            )
            components = tuple(
                ConfidenceComponent(
                    str(item.get("component") or "unknown"),
                    float(item.get("value") or 0),
                    str(item.get("reason") or ""),
                )
                for item in data.get("confidence_components", [])
                if isinstance(item, dict)
            )
            hypotheses = tuple(
                EntityHypothesis(
                    EntityType(str(item["entity_type"])),
                    str(item["normalized_value"]),
                    float(item.get("confidence") or 0),
                    tuple(item.get("reasons", [])),
                )
                for item in data.get("hypotheses", [])
                if isinstance(item, dict)
            )
            return NormalizedEntity(
                entity_type=entity_type,
                normalized_value=str(data["normalized_value"]),
                confidence=float(data.get("confidence") or 0),
                raw_values=tuple(str(value) for value in data.get("raw_values", [])),
                sources=sources,
                confidence_components=components,
                attributes=dict(data.get("attributes") or {}),
                hypotheses=hypotheses,
            )
        except (KeyError, TypeError, ValueError):
            return None

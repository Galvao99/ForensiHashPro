from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.contracts.analysis import (
    AnalysisContract,
    AnalysisState,
    ContractError,
    Fact,
    FindingContract,
    Limitation,
    SCHEMA_VERSION,
)
from app.models import AnalysisResult
from app.processing import ProcessingStatus


def _id(analysis_id: str, category: str, code: str, index: int) -> str:
    return str(uuid5(NAMESPACE_URL, f"forensihash:{analysis_id}:{category}:{code}:{index}"))


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _plain(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(item) for item in value]
    return str(value)


class LegacyAnalysisAdapter:
    """Converte uma análise individual legada sem importar Qt.

    Resultados de correlação e comparação multi-evidência não pertencem a
    esta adaptação. Seções não executadas permanecem ``None`` e recebem uma
    etapa ``SKIPPED`` explícita no contrato.
    """

    def convert(self, result: AnalysisResult) -> AnalysisContract:
        analysis_id = result.analysis_id or str(
            uuid5(NAMESPACE_URL, f"forensihash:legacy:{result.hashes.sha256}")
        )
        evidence = result.evidence_source
        evidence_id = evidence.evidence_id if evidence else str(
            uuid5(NAMESPACE_URL, f"forensihash:evidence:{result.hashes.sha256}")
        )

        facts = self._facts(result, analysis_id)
        findings = [
            FindingContract(
                finding_id=_id(analysis_id, "finding", finding.category, index),
                rule_id=f"legacy.{finding.category.lower().replace(' ', '_')}",
                severity=finding.severity.value,
                title=finding.title,
                statement=finding.description,
                evidence_refs=[evidence_id],
                recommendation=finding.recommendation,
                confidence=finding.score,
            )
            for index, finding in enumerate(result.findings)
        ]
        limitations, errors = self._issues(result, analysis_id)
        statuses = {step.status for step in result.processing_steps}
        state = (
            AnalysisState.COMPROMISED
            if evidence and evidence.capture_state.value == "compromised"
            else AnalysisState.FAILED
            if ProcessingStatus.FAILED in statuses and not facts
            else AnalysisState.PARTIAL
            if statuses.intersection(
                {ProcessingStatus.FAILED, ProcessingStatus.PARTIAL, ProcessingStatus.LIMIT_EXCEEDED}
            )
            else AnalysisState.COMPLETED
        )
        text_source = self._text_source(result)
        text_payload = {"text": result.extracted_text, "source": text_source}

        return AnalysisContract(
            schema_version=SCHEMA_VERSION,
            analysis_id=analysis_id,
            evidence_id=evidence_id,
            state=state,
            file={
                "name": result.file_info.name,
                "extension": result.file_info.extension,
                "size_bytes": result.file_info.size_bytes,
                "created_at": result.file_info.created_at,
                "modified_at": result.file_info.modified_at,
                "accessed_at": result.file_info.accessed_at,
            },
            hashes=_plain(result.hashes),
            declared_type=evidence.declared_type if evidence else result.file_info.extension,
            detected_type=(
                evidence.detected_type
                if evidence
                else getattr(result.magic_numbers, "detected_format", None)
            ),
            metadata=_plain(result.metadata.raw),
            technical_structure={
                "integrity": _plain(result.integrity),
                "pdf": _plain(result.pdf_structure),
                "binary": _plain(result.binary_analysis),
                "json": _plain(result.json_analysis),
            },
            native_text=text_payload if text_source.startswith("native") else None,
            ocr=text_payload if text_source == "ocr" else None,
            signatures=[_plain(result.digital_signature)],
            ip_addresses=None,
            timeline=(
                [_plain(event) for event in result.timeline_events]
                if result.timeline_events
                else None
            ),
            comparison=None,
            biometrics=_plain(result.biometric_report),
            facts=facts,
            findings=findings,
            limitations=limitations,
            errors=errors,
            external_results=None,
            processing_steps=[
                self._step(step, analysis_id, index)
                for index, step in enumerate(result.processing_steps)
            ] + self._scope_steps(result, analysis_id),
            execution={
                "started_at": result.analyzed_at,
                "finished_at": result.completed_at or datetime.now(timezone.utc),
                "engine_versions": {"legacy_adapter": "1"},
                "rule_versions": {"forensic_rules": "2026.08"},
                "integrations": self._integrations(result),
                "runtime": "python",
            },
        )

    def _facts(self, result: AnalysisResult, analysis_id: str) -> list[Fact]:
        values = [
            ("file_identification", "filesystem", _plain(result.file_info)),
            ("hashes", "hash_engine", _plain(result.hashes)),
            ("type_detection", "magic_number_engine", _plain(result.magic_numbers)),
            ("metadata", "metadata_engine", _plain(result.metadata.raw)),
            ("signature_detection", "digital_signature_engine", _plain(result.digital_signature)),
        ]
        if result.binary_analysis is not None:
            values.append(("binary_structure", "binary_structure_engine", _plain(result.binary_analysis)))
        if result.pdf_structure is not None:
            values.append(("pdf_structure", "pdf_structure_engine", _plain(result.pdf_structure)))
        return [
            Fact(_id(analysis_id, "fact", kind, index), kind, source, data)
            for index, (kind, source, data) in enumerate(values)
        ]

    def _issues(
        self, result: AnalysisResult, analysis_id: str
    ) -> tuple[list[Limitation], list[ContractError]]:
        limitations: list[Limitation] = []
        errors: list[ContractError] = []
        index = 0
        for step in result.processing_steps:
            for issue in step.issues:
                if issue.status in {
                    ProcessingStatus.UNAVAILABLE,
                    ProcessingStatus.SKIPPED,
                    ProcessingStatus.LIMIT_EXCEEDED,
                    ProcessingStatus.PARTIAL,
                }:
                    limitations.append(
                        Limitation(
                            _id(analysis_id, "limitation", issue.code, index),
                            issue.code,
                            issue.component,
                            issue.user_message,
                            issue.impact.value,
                        )
                    )
                else:
                    errors.append(
                        ContractError(
                            _id(analysis_id, "error", issue.code, index),
                            issue.code,
                            issue.component,
                            issue.user_message,
                            issue.impact.value,
                            issue.occurred_at_utc,
                            _plain(issue.details),
                        )
                    )
                index += 1
        return limitations, errors

    @staticmethod
    def _step(step: Any, analysis_id: str, index: int) -> dict[str, Any]:
        return {
            "step_id": _id(analysis_id, "step", step.code, index),
            "code": step.code,
            "component": step.component,
            "status": step.status.value,
            "technical_message": step.technical_message,
            "user_message": step.user_message,
            "started_at": step.started_at_utc,
            "finished_at": step.finished_at_utc,
            "duration_ms": step.duration_ms,
            "safe_details": _plain(step.safe_details),
        }

    @staticmethod
    def _text_source(result: AnalysisResult) -> str:
        for step in reversed(result.processing_steps):
            if step.code == "text_extraction" and step.value is not None:
                return str(getattr(step.value, "source", "unknown"))
        return "legacy_unknown" if result.extracted_text else "none"

    @staticmethod
    def _scope_steps(result: AnalysisResult, analysis_id: str) -> list[dict[str, Any]]:
        """Declara seções ausentes sem apresentá-las como coleções executadas."""
        offset = len(result.processing_steps)
        sections = [
            (
                "ip_context",
                "Consulta externa de IP não integra a análise individual.",
                "not_part_of_individual_analysis",
            ),
            (
                "comparison",
                "Comparação entre evidências possui resultado separado.",
                "different_scope",
            ),
            (
                "external_results",
                "Nenhuma integração externa individual foi executada neste fluxo.",
                "not_executed",
            ),
        ]
        if not result.timeline_events:
            sections.append(
                (
                    "timeline",
                    "Timeline não foi executada no fluxo individual.",
                    "not_executed",
                )
            )
        return [
            {
                "step_id": _id(analysis_id, "step", code, offset + index),
                "code": code,
                "component": code,
                "status": ProcessingStatus.SKIPPED.value,
                "technical_message": message,
                "user_message": message,
                "started_at": result.completed_at or result.analyzed_at,
                "finished_at": result.completed_at or result.analyzed_at,
                "duration_ms": 0,
                "safe_details": {"reason": reason, "scope": "individual_evidence"},
            }
            for index, (code, message, reason) in enumerate(sections)
        ]

    @staticmethod
    def _integrations(result: AnalysisResult) -> list[str]:
        integrations: list[str] = []
        if any(step.component == "metadata" for step in result.processing_steps):
            integrations.append("exiftool")
        source = LegacyAnalysisAdapter._text_source(result)
        if source == "ocr":
            integrations.extend(["tesseract", "poppler"])
        return integrations

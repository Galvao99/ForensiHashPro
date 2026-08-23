from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
import logging
from uuid import uuid4

from app.engines.file_analyzer import FileAnalyzer
from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.services.correlation_service import CorrelationService
from app.services.text_extraction_service import (
    TextExtractionService,
)
from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.evidence import CaptureState, EvidenceIntegrityError, EvidenceManager
from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)
from app.processing.logging import log_step
from app.entities.service import EntityExtractionService
from app.services.text_extraction_service import TextExtractionResult
from app.services.timeline_service import TimelineService
from app.analysis_profiles import (
    AnalysisCapability,
    AnalysisProfile,
    FORENSIHASH_PRO,
)


LOGGER = logging.getLogger("forensihash.processing")


class AnalysisService:
    """
    Coordena a análise individual dos arquivos e a investigação
    correlacionada do conjunto de resultados.
    """

    def __init__(
        self,
        analyzer: FileAnalyzer,
        correlation_service: CorrelationService | None = None,
        text_extraction_service: TextExtractionService | None = None,
        evidence_manager: EvidenceManager | None = None,
        entity_extraction_service: EntityExtractionService | None = None,
        timeline_service: TimelineService | None = None,
        profile: AnalysisProfile = FORENSIHASH_PRO,
    ) -> None:
        self.profile = profile
        self.analyzer = analyzer

        self.correlation_service = (
            correlation_service
            if correlation_service is not None
            else CorrelationService()
        )

        self.text_extraction_service = text_extraction_service
        if self.text_extraction_service is None and profile.allows(
            AnalysisCapability.CONTENT_EXTRACTION
        ):
            self.text_extraction_service = TextExtractionService()

        self.evidence_manager = evidence_manager or EvidenceManager()
        self.entity_extraction_service = entity_extraction_service
        if self.entity_extraction_service is None and profile.allows(
            AnalysisCapability.ENTITY_EXTRACTION
        ):
            self.entity_extraction_service = EntityExtractionService()
        self.timeline_service = timeline_service
        if self.timeline_service is None and profile.allows(
            AnalysisCapability.TEMPORAL_ANALYSIS
        ):
            self.timeline_service = TimelineService()

    def analyze(
        self,
        file_path: Path,
        *,
        analysis_id: str | None = None,
    ) -> AnalysisResult:
        """
        Executa a análise técnica e armazena o texto extraído
        no próprio AnalysisResult.
        """

        started_at = datetime.now(timezone.utc)
        analysis_id = analysis_id or str(uuid4())
        with self.evidence_manager.acquire(file_path) as lease:
            evidence = lease.source
            working_path = evidence.working_path
            result = self.analyzer.analyze_acquired(evidence)
            result.analysis_id = analysis_id
            result.analysis_profile = self.profile.name.value
            result.analyzed_at = started_at

            extract_step = getattr(self.text_extraction_service, "extract", None)
            if not self.profile.allows(AnalysisCapability.CONTENT_EXTRACTION):
                text_step = self._capability_skipped(
                    "text_extraction", "text_extraction",
                    AnalysisCapability.CONTENT_EXTRACTION,
                )
                result.processing_steps.append(text_step)
                result.processing_steps.append(self._capability_skipped(
                    "ocr", "ocr", AnalysisCapability.OCR,
                ))
                result.extracted_text = ""
            elif callable(extract_step):
                text_step = extract_step(working_path)
                result.processing_steps.append(text_step)
                result.extracted_text = (
                    text_step.value.text if text_step.value is not None else ""
                )
            else:
                try:
                    result.extracted_text = (
                        self.text_extraction_service.extract_text(working_path)
                    )
                    text_step = StepResult(
                        code="text_extraction",
                        component="text_extraction",
                        status=(
                            ProcessingStatus.SUCCESS
                            if result.extracted_text
                            else ProcessingStatus.NO_FINDINGS
                        ),
                        technical_message="Extração textual legada concluída.",
                        user_message="Extração textual concluída.",
                    )
                except Exception as error:
                    issue = ProcessingIssue(
                        code="text_extraction_failed",
                        status=ProcessingStatus.FAILED,
                        technical_message="Extração textual legada falhou.",
                        user_message="A extração textual não pôde ser concluída.",
                        component="text_extraction",
                        details={"error_type": type(error).__name__},
                        impact=ProcessingImpact.ANALYSIS_PARTIAL,
                        original_exception=error,
                    )
                    text_step = StepResult(
                        code="text_extraction",
                        component="text_extraction",
                        status=ProcessingStatus.FAILED,
                        technical_message=issue.technical_message,
                        user_message=issue.user_message,
                        issues=[issue],
                    )
                    result.extracted_text = ""
                result.processing_steps.append(text_step)

            evidence = evidence.with_detected_type(
                getattr(result.magic_numbers, "detected_format", None)
            )
            lease.source = evidence
            evidence = lease.verify()

            if result.hashes.sha256 != evidence.initial_sha256:
                evidence = evidence.compromised(
                    "O SHA-256 calculado pelo motor diverge da aquisição.",
                    final_sha256=evidence.final_sha256,
                )
                lease.source = evidence

            result.evidence_source = evidence
            result.file_info = replace(
                result.file_info,
                name=evidence.original_name,
                path=evidence.original_path,
                extension=evidence.original_path.suffix.lower(),
                size_bytes=evidence.size_bytes,
                created_at=datetime.fromtimestamp(
                    evidence.original_identity.changed_ns / 1_000_000_000,
                    tz=timezone.utc,
                ),
                modified_at=datetime.fromtimestamp(
                    evidence.original_identity.modified_ns / 1_000_000_000,
                    tz=timezone.utc,
                ),
                accessed_at=datetime.fromtimestamp(
                    evidence.original_identity.accessed_ns / 1_000_000_000,
                    tz=timezone.utc,
                ),
            )

            if not self.profile.allows(AnalysisCapability.ENTITY_EXTRACTION):
                result.processing_steps.append(self._capability_skipped(
                    "entity_resolution", "entity_extraction",
                    AnalysisCapability.ENTITY_EXTRACTION,
                ))
            else:
                try:
                    text_result = (
                        text_step.value
                        if isinstance(text_step.value, TextExtractionResult)
                        else None
                    )
                    resolution = self.entity_extraction_service.resolve_analysis(  # type: ignore[union-attr]
                        result,
                        text_result=text_result,
                    )
                    result.resolved_entities = list(resolution.entities)
                    result.processing_steps.append(
                        StepResult(
                            code="entity_resolution",
                            component="entity_extraction",
                            status=(
                                ProcessingStatus.SUCCESS
                                if resolution.entities
                                else ProcessingStatus.NO_FINDINGS
                            ),
                            technical_message="Candidatos de entidade avaliados pelo resolver V2.",
                            user_message="Extração de entidades concluída.",
                            value=resolution,
                            safe_details={
                                "candidate_count": len(resolution.candidates),
                                "entity_count": len(resolution.entities),
                            },
                        )
                    )
                except Exception as error:
                    issue = ProcessingIssue(
                        code="entity_resolution_failed",
                        status=ProcessingStatus.FAILED,
                        technical_message="O Entity Resolver V2 não concluiu o processamento.",
                        user_message="A extração estruturada de entidades não pôde ser concluída.",
                        component="entity_extraction",
                        details={"error_type": type(error).__name__},
                        impact=ProcessingImpact.ANALYSIS_PARTIAL,
                        original_exception=error,
                    )
                    result.processing_steps.append(
                        StepResult(
                            code="entity_resolution",
                            component="entity_extraction",
                            status=ProcessingStatus.FAILED,
                            technical_message=issue.technical_message,
                            user_message=issue.user_message,
                            issues=[issue],
                        )
                    )

            if not self.profile.allows(AnalysisCapability.IP_ANALYSIS):
                result.processing_steps.append(self._capability_skipped(
                    "ip_context", "ip_analysis", AnalysisCapability.IP_ANALYSIS,
                ))

            if evidence.capture_state is CaptureState.COMPROMISED:
                raise EvidenceIntegrityError(
                    "A evidência mudou durante a análise; resultados parciais "
                    "não podem ser correlacionados.",
                    evidence=evidence,
                    partial_result=result,
                )

            result.completed_at = datetime.now(timezone.utc)
            if not self.profile.allows(AnalysisCapability.TEMPORAL_ANALYSIS):
                result.processing_steps.append(self._capability_skipped(
                    "timeline", "timeline", AnalysisCapability.TEMPORAL_ANALYSIS,
                ))
            else:
              try:
                timeline = self.timeline_service.build(result)  # type: ignore[union-attr]
                result.timeline_events = timeline.events
                result.timeline_warnings = timeline.warnings
                result.timeline_limitations = timeline.limitations
                result.processing_steps.append(
                    StepResult(
                        code="timeline",
                        component="timeline",
                        status=(
                            ProcessingStatus.SUCCESS
                            if timeline.events
                            else ProcessingStatus.NO_FINDINGS
                        ),
                        technical_message="Timeline V2 construída sobre resultados existentes.",
                        user_message="Linha do tempo técnica construída.",
                        value=timeline,
                        safe_details=timeline.summary,
                    )
                )
              except Exception as error:
                issue = ProcessingIssue(
                    code="timeline_failed",
                    status=ProcessingStatus.PARTIAL,
                    technical_message="A Timeline V2 não pôde ser construída.",
                    user_message="A linha do tempo técnica ficou indisponível.",
                    component="timeline",
                    details={"error_type": type(error).__name__},
                    impact=ProcessingImpact.ANALYSIS_PARTIAL,
                    original_exception=error,
                )
                result.processing_steps.append(
                    StepResult(
                        code="timeline", component="timeline",
                        status=ProcessingStatus.PARTIAL,
                        technical_message=issue.technical_message,
                        user_message=issue.user_message, issues=[issue],
                    )
                )

            for step in result.processing_steps:
                log_step(
                    LOGGER,
                    step,
                    analysis_id=analysis_id,
                    evidence_id=evidence.evidence_id,
                )

            return result

    def correlate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """
        Executa a investigação sobre um ou mais arquivos.
        """

        if not self.profile.allows(AnalysisCapability.CROSS_ARTIFACT_CORRELATION):
            raise PermissionError("Correlação entre artefatos não habilitada neste perfil.")
        result_list = list(results)

        compromised = next(
            (
                item
                for item in result_list
                if item.evidence_source is not None
                and item.evidence_source.capture_state is CaptureState.COMPROMISED
            ),
            None,
        )
        if compromised is not None:
            raise EvidenceIntegrityError(
                "Resultado comprometido não pode participar da correlação.",
                evidence=compromised.evidence_source,
                partial_result=compromised,
            )

        if not result_list:
            return CorrelationResult()

        correlation_result = (
            self.correlation_service.analyze(
                result_list
            )
        )

        self._print_correlation_result(
            correlation_result
        )

        return correlation_result

    def investigate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        return self.correlate(results)

    def correlate_case(
        self,
        case_id: str,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        if not self.profile.allows(AnalysisCapability.CROSS_ARTIFACT_CORRELATION):
            raise PermissionError("Correlação entre artefatos não habilitada neste perfil.")
        return self.correlation_service.update_case(case_id, results)

    def build_investigation_context(
        self,
        results: Sequence[AnalysisResult],
    ) -> InvestigationContext:
        """
        Consolida os resultados já analisados para uso pelas páginas
        que precisam acessar os dados investigativos estruturados.

        Não executa novamente OCR nem análise técnica dos arquivos.
        """

        return self.correlation_service.build_context(
            list(results)
        )

    def _print_correlation_result(
        self,
        correlation_result: CorrelationResult,
    ) -> None:
        print(
            "Correlação consistente:",
            correlation_result.is_consistent,
        )

        print(
            "Resumo da correlação:",
            correlation_result.summary,
        )

        for finding in correlation_result.findings:
            severity = self._normalize_severity(
                getattr(
                    finding,
                    "severity",
                    "info",
                )
            )

            description = getattr(
                finding,
                "description",
                "",
            )

            metadata = getattr(
                finding,
                "metadata",
                {},
            )

            print("-" * 60)
            print(
                f"[{severity.upper()}] "
                f"{finding.title}"
            )
            print(description)
            print(metadata)

    @staticmethod
    def _normalize_severity(
        severity: object,
    ) -> str:
        value = getattr(
            severity,
            "value",
            severity,
        )

        normalized = str(value).strip().lower()

        aliases = {
            "success": "ok",
            "warn": "warning",
            "danger": "critical",
            "error": "critical",
        }

        return aliases.get(
            normalized,
            normalized or "info",
        )

    @staticmethod
    def _capability_skipped(
        code: str,
        component: str,
        capability: AnalysisCapability,
    ) -> StepResult:
        message = "Etapa não executada porque a capability não está habilitada no perfil de análise."
        return StepResult(
            code=code,
            component=component,
            status=ProcessingStatus.SKIPPED,
            technical_message=message,
            user_message=message,
            safe_details={
                "reason": "capability_not_enabled",
                "capability": capability.value,
            },
        )

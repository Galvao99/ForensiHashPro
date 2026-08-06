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
    ) -> None:
        self.analyzer = analyzer

        self.correlation_service = (
            correlation_service
            if correlation_service is not None
            else CorrelationService()
        )

        self.text_extraction_service = (
            text_extraction_service
            if text_extraction_service is not None
            else TextExtractionService()
        )

        self.evidence_manager = evidence_manager or EvidenceManager()

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
            result = self.analyzer.analyze(working_path)
            result.analysis_id = analysis_id
            result.analyzed_at = started_at

            extract_step = getattr(self.text_extraction_service, "extract", None)
            if callable(extract_step):
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

            if evidence.capture_state is CaptureState.COMPROMISED:
                raise EvidenceIntegrityError(
                    "A evidência mudou durante a análise; resultados parciais "
                    "não podem ser correlacionados.",
                    evidence=evidence,
                    partial_result=result,
                )

            for step in result.processing_steps:
                log_step(
                    LOGGER,
                    step,
                    analysis_id=analysis_id,
                    evidence_id=evidence.evidence_id,
                )

            result.completed_at = datetime.now(timezone.utc)
            return result

    def correlate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """
        Executa a investigação sobre um ou mais arquivos.
        """

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

from pathlib import Path
from typing import Sequence

from app.engines.file_analyzer import FileAnalyzer
from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.services.correlation_service import CorrelationService
from app.services.text_extraction_service import (
    TextExtractionService,
)


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

    def analyze(
        self,
        file_path: Path,
    ) -> AnalysisResult:
        """
        Executa a análise técnica e armazena o texto extraído
        no próprio AnalysisResult.
        """

        result = self.analyzer.analyze(file_path)

        try:
            result.extracted_text = (
                self.text_extraction_service.extract_text(
                    file_path
                )
            )

        except Exception as error:
            print(
                "Falha durante a extração textual de "
                f"{file_path.name}: {error}"
            )

            result.extracted_text = ""

        return result

    def correlate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """
        Executa a investigação sobre um ou mais arquivos.
        """

        result_list = list(results)

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
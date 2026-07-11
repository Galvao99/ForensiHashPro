from pathlib import Path
from typing import Sequence

from app.engines.file_analyzer import FileAnalyzer
from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.services.correlation_service import CorrelationService


class AnalysisService:
    """
    Coordena a análise individual dos arquivos e a investigação
    correlacionada do conjunto de resultados.

    O ForensiHash não salva análises automaticamente.
    Exportações devem ser ações explícitas do usuário.
    """

    def __init__(
        self,
        analyzer: FileAnalyzer,
        correlation_service: CorrelationService | None = None,
    ) -> None:
        self.analyzer = analyzer

        self.correlation_service = (
            correlation_service
            if correlation_service is not None
            else CorrelationService()
        )

    def analyze(
        self,
        file_path: Path,
    ) -> AnalysisResult:
        """
        Executa a análise técnica individual de um arquivo.
        """

        return self.analyzer.analyze(file_path)

    def correlate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """
        Executa a investigação sobre o conjunto de arquivos analisados.
        """

        result_list = list(results)

        if not result_list:
            return CorrelationResult()

        correlation_result = self.correlation_service.analyze(
            result_list
        )

        self._print_correlation_result(
            correlation_result
        )

        return correlation_result

    def investigate(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """
        Nome alternativo para a execução da investigação.
        """

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
                None,
            )

            if not description:
                description = getattr(
                    finding,
                    "message",
                    "",
                )

            metadata = getattr(
                finding,
                "metadata",
                None,
            )

            if metadata is None:
                metadata = getattr(
                    finding,
                    "evidence",
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
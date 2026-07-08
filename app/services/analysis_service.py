from pathlib import Path

from app.engines.file_analyzer import FileAnalyzer
from app.models import AnalysisResult
from app.services.correlation_service import CorrelationService


class AnalysisService:
    """
    Coordena o fluxo de análise sem persistir dados automaticamente.

    O ForensiHash não salva análises por padrão.
    Exportações devem ser ser ações explícitas do usuário.
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

    def analyze(self, file_path: Path) -> AnalysisResult:
        result = self.analyzer.analyze(file_path)

        correlation_result = self.correlation_service.analyze([result])

        print("Correlação consistente:", correlation_result.is_consistent)

        for finding in correlation_result.findings:
            print("-" * 60)
            print(f"[{finding.severity.upper()}] {finding.title}")
            print(finding.message)
            print(finding.evidence)

        return result
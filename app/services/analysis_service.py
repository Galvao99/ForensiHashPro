from pathlib import Path

from app.engines.file_analyzer import FileAnalyzer
from app.models import AnalysisResult


class AnalysisService:
    """
    Coordena o fluxo de análise sem persistir dados automaticamente.

    O ForensiHash não salva análises por padrão.
    Exportações devem ser ações explícitas do usuário.
    """

    def __init__(self, analyzer: FileAnalyzer) -> None:
        self.analyzer = analyzer

    def analyze(self, file_path: Path) -> AnalysisResult:
        return self.analyzer.analyze(file_path)
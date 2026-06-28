from app.models import AnalysisResult
from app.models.comparison_result import ComparisonResult
from app.models.comparison_section import ComparisonSection


class ComparisonEngine:
    """Responsável pela comparação entre duas análises forenses."""

    def compare(
        self,
        left: AnalysisResult,
        right: AnalysisResult,
    ) -> ComparisonResult:

        return ComparisonResult()
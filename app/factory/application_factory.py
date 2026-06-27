from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.metadata_engine import MetadataEngine
from app.services.analysis_service import AnalysisService


class ApplicationFactory:
    """Monta as dependências principais da aplicação."""

    @staticmethod
    def create_analysis_service() -> AnalysisService:
        hash_engine = HashEngine()
        metadata_engine = MetadataEngine()
        findings_engine = FindingsEngine()

        analyzer = FileAnalyzer(
            hash_engine=hash_engine,
            metadata_engine=metadata_engine,
            findings_engine=findings_engine,
        )

        return AnalysisService(analyzer)
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.services.analysis_service import AnalysisService


class ApplicationFactory:
    """Monta as dependências principais da aplicação."""

    @staticmethod
    def create_analysis_service() -> AnalysisService:
        hash_engine = HashEngine()
        metadata_engine = MetadataEngine()
        findings_engine = FindingsEngine()
        magic_number_engine = MagicNumberEngine()
        digital_signature_engine = DigitalSignatureEngine()
        pdf_structure_engine = PDFStructureEngine()

        analyzer = FileAnalyzer(
            hash_engine=hash_engine,
            metadata_engine=metadata_engine,
            findings_engine=findings_engine,
            magic_number_engine=magic_number_engine,
            digital_signature_engine=digital_signature_engine,
            pdf_structure_engine=pdf_structure_engine,
        )

        return AnalysisService(analyzer)
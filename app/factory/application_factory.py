from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.services.analysis_service import AnalysisService
from app.engines.binary_structure_engine import BinaryStructureEngine
from app.biometric.parsers import (
    AwareKnomiReportParser,
    BiometricParserRegistry,
)
from app.services.biometric_report_service import BiometricReportService
from app.settings import ApplicationPaths, SettingsService, ToolDetector
from app.services.text_extraction_service import TextExtractionService
from app.evidence import EvidenceManager
from app.binary.parsers import PdfRawParser
from app.application import AnalysisCoordinator


class ApplicationFactory:
    """Monta as dependências principais da aplicação."""

    @staticmethod
    def create_analysis_service() -> AnalysisService:
        paths = ApplicationPaths.discover()
        settings = SettingsService(paths=paths).load()
        tools = ToolDetector(paths)
        hash_engine = HashEngine()
        metadata_engine = MetadataEngine(
            tool_status=tools.exiftool(enabled=settings.metadata_enabled),
            timeout_seconds=settings.limits.external_tool_timeout_seconds,
            max_output_bytes=settings.limits.max_external_output_bytes,
        )
        findings_engine = FindingsEngine()
        magic_number_engine = MagicNumberEngine()
        digital_signature_engine = DigitalSignatureEngine()
        pdf_structure_engine = PDFStructureEngine()
        binary_structure_engine = BinaryStructureEngine(
            string_maximum_results=settings.limits.max_binary_strings,
            pdf_raw_parser=PdfRawParser(
                max_objects=settings.limits.max_pdf_objects
            ),
        )
        biometric_registry = BiometricParserRegistry(
            [AwareKnomiReportParser()]
        )
        biometric_report_service = BiometricReportService(
            biometric_registry
        )

        analyzer = FileAnalyzer(
            hash_engine=hash_engine,
            metadata_engine=metadata_engine,
            findings_engine=findings_engine,
            magic_number_engine=magic_number_engine,
            digital_signature_engine=digital_signature_engine,
            pdf_structure_engine=pdf_structure_engine,
            binary_structure_engine=binary_structure_engine,
            biometric_report_service=biometric_report_service,
        )

        text_extraction_service = TextExtractionService(
            tesseract_status=tools.tesseract(enabled=settings.ocr_enabled),
            poppler_status=tools.poppler(enabled=settings.ocr_enabled),
            limits=settings.limits,
        )

        return AnalysisService(
            analyzer,
            text_extraction_service=text_extraction_service,
            evidence_manager=EvidenceManager(
                paths.temp_dir / "evidence",
                max_file_size_bytes=settings.limits.max_file_size_bytes,
            ),
        )

    @staticmethod
    def create_analysis_coordinator() -> AnalysisCoordinator:
        """Composição reutilizável sem criar QObject, janela ou widget."""
        return AnalysisCoordinator(ApplicationFactory.create_analysis_service())

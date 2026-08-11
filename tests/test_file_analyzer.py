from pathlib import Path

from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.models import AnalysisResult
from app.models import MetadataResult
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.contracts import AnalysisState, LegacyAnalysisAdapter
from app.processing import ProcessingStatus, StepResult


class TestFileAnalyzer:
    def test_analyze(self, tmp_path: Path) -> None:
        test_file = tmp_path / "arquivo.txt"
        test_file.write_text("ForensiHash", encoding="utf-8")

        hash_engine = HashEngine()
        findings_engine = FindingsEngine()
        metadata_engine = MetadataEngine()
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

        result = analyzer.analyze_fixture(test_file)

        assert isinstance(result, AnalysisResult)
        assert isinstance(result.findings, list)
        assert result.file_info.name == "arquivo.txt"
        assert result.file_info.size_bytes == test_file.stat().st_size
        assert result.hashes.md5
        assert result.hashes.sha1
        assert result.hashes.sha224
        assert result.hashes.sha256
        assert result.hashes.sha384
        assert result.hashes.sha512
        assert result.metadata.raw
        assert result.magic_numbers
        assert result.digital_signature

    def test_individual_engine_failure_produces_partial_contract(
        self, tmp_path: Path
    ) -> None:
        test_file = tmp_path / "engine-failure.txt"
        test_file.write_text("ForensiHash", encoding="utf-8")

        class Metadata:
            @staticmethod
            def extract_step(_path):
                return StepResult(
                    code="metadata_extraction",
                    component="metadata",
                    status=ProcessingStatus.SUCCESS,
                    technical_message="ok",
                    user_message="ok",
                    value=MetadataResult(raw={}),
                )

        class FailingMagic:
            @staticmethod
            def analyze(_path):
                raise RuntimeError("synthetic engine failure")

        analyzer = FileAnalyzer(
            hash_engine=HashEngine(),
            metadata_engine=Metadata(),
            findings_engine=FindingsEngine(),
            magic_number_engine=FailingMagic(),
            digital_signature_engine=DigitalSignatureEngine(),
            pdf_structure_engine=PDFStructureEngine(),
        )

        result = analyzer.analyze_fixture(test_file)
        result.analysis_id = "partial-analysis"
        contract = LegacyAnalysisAdapter().convert(result)

        assert contract.state is AnalysisState.PARTIAL
        assert any(error.code == "magic_number_failed" for error in contract.errors)
        assert any(
            step["component"] == "magic_number" and step["status"] == "failed"
            for step in contract.processing_steps
        )

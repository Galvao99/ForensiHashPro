from pathlib import Path
from app.engines.binary_structure_engine import BinaryStructureEngine
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.models.analysis_result import AnalysisResult


class _RecordingBinaryEngine:
    def __init__(self) -> None:
        self.calls: list[Path] = []
        self.delegate = BinaryStructureEngine()

    def analyze(self, path: Path):
        self.calls.append(path)
        return self.delegate.analyze(path)


def _analyzer(binary_engine=None) -> FileAnalyzer:
    return FileAnalyzer(
        hash_engine=HashEngine(),
        metadata_engine=MetadataEngine(),
        findings_engine=FindingsEngine(),
        magic_number_engine=MagicNumberEngine(),
        digital_signature_engine=DigitalSignatureEngine(),
        pdf_structure_engine=PDFStructureEngine(),
        binary_structure_engine=binary_engine,
    )


def test_file_analyzer_runs_binary_once_and_keeps_old_analyses(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("ForensiHash binary foundation", encoding="utf-8")
    binary_engine = _RecordingBinaryEngine()
    result = _analyzer(binary_engine).analyze(path)
    assert binary_engine.calls == [path]
    assert result.binary_analysis is not None
    assert result.binary_analysis.file_size == path.stat().st_size
    assert result.hashes.sha256
    assert result.metadata.raw
    assert result.magic_numbers is not None
    assert result.digital_signature is not None
    assert result.integrity is not None


def test_optional_binary_engine_preserves_compatibility(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("legacy construction", encoding="utf-8")
    result = _analyzer().analyze(path)
    assert result.binary_analysis is None


class _FailingBinaryEngine:
    def analyze(self, path: Path):
        raise RuntimeError("controlled failure")


def test_binary_failure_does_not_abort_main_analysis(tmp_path: Path) -> None:
    path = tmp_path / "sample.txt"
    path.write_text("main analysis survives", encoding="utf-8")
    result = _analyzer(_FailingBinaryEngine()).analyze(path)
    assert result.binary_analysis is None
    assert result.hashes.sha256


def test_analysis_result_binary_default_is_none() -> None:
    fields = AnalysisResult.__dataclass_fields__
    assert fields["binary_analysis"].default is None

from pathlib import Path

from app.engines.file_analyzer import FileAnalyzer
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.metadata_engine import MetadataEngine
from app.models import AnalysisResult


class TestFileAnalyzer:
    def test_analyze(self, tmp_path: Path) -> None:
        test_file = tmp_path / "arquivo.txt"
        test_file.write_text("ForensiHash", encoding="utf-8")

        hash_engine = HashEngine()
        findings_engine = FindingsEngine()
        metadata_engine = MetadataEngine()
        analyzer = FileAnalyzer(hash_engine, metadata_engine, findings_engine)        

        result = analyzer.analyze(test_file)

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
from datetime import datetime
from pathlib import Path

from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.metadata_engine import MetadataEngine
from app.models import AnalysisResult, FileInfo


class FileAnalyzer:
    """
    Responsável por coordenar a análise técnica completa de um arquivo.
    """

    def __init__(
        self,
        hash_engine: HashEngine,
        metadata_engine: MetadataEngine,
        findings_engine: FindingsEngine,
    ) -> None:
        self.hash_engine = hash_engine
        self.metadata_engine = metadata_engine
        self.findings_engine = findings_engine

    def analyze(self, file_path: Path) -> AnalysisResult:
        stat = file_path.stat()

        file_info = FileInfo(
            name=file_path.name,
            path=file_path,
            extension=file_path.suffix,
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(stat.st_ctime),
            modified_at=datetime.fromtimestamp(stat.st_mtime),
            accessed_at=datetime.fromtimestamp(stat.st_atime),
        )

        hashes = self.hash_engine.calculate_all(file_path)
        metadata = self.metadata_engine.extract(file_path)
        findings = self.findings_engine.analyze(metadata)

        return AnalysisResult(
            file_info=file_info,
            hashes=hashes,
            metadata=metadata,
            findings=findings,
        )
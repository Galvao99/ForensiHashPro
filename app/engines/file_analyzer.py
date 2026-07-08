from datetime import datetime
from pathlib import Path

from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.models import AnalysisResult, FileInfo
from app.models.integrity_result import IntegrityResult


class FileAnalyzer:
    """
    Responsável por coordenar a análise técnica completa de um arquivo.
    """

    def __init__(
        self,
        hash_engine: HashEngine,
        metadata_engine: MetadataEngine,
        findings_engine: FindingsEngine,
        magic_number_engine: MagicNumberEngine,
        digital_signature_engine: DigitalSignatureEngine,
        pdf_structure_engine: PDFStructureEngine,
    ) -> None:
        self.hash_engine = hash_engine
        self.metadata_engine = metadata_engine
        self.findings_engine = findings_engine
        self.magic_number_engine = magic_number_engine
        self.digital_signature_engine = digital_signature_engine
        self.pdf_structure_engine = pdf_structure_engine

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
        magic_numbers = self.magic_number_engine.analyze(file_path)
        digital_signature = self.digital_signature_engine.analyze(file_path)
        pdf_structure = self.pdf_structure_engine.analyze(file_path)

        integrity = self._build_integrity_result(
            hashes=hashes,
            magic_numbers=magic_numbers,
            digital_signature=digital_signature,
            pdf_structure=pdf_structure,
        )

        findings = self.findings_engine.analyze(
            metadata=metadata,
            integrity=integrity,
        )

        return AnalysisResult(
            file_info=file_info,
            hashes=hashes,
            metadata=metadata,
            findings=findings,
            magic_numbers=magic_numbers,
            digital_signature=digital_signature,
            integrity=integrity,
        )

    def _build_integrity_result(
        self,
        hashes,
        magic_numbers,
        digital_signature,
        pdf_structure,
    ) -> IntegrityResult:
        hash_verified = bool(getattr(hashes, "sha256", None))

        magic_number_verified = bool(
            getattr(magic_numbers, "is_match", False)
            or getattr(magic_numbers, "matches_extension", False)
            or getattr(magic_numbers, "is_valid", False)
        )

        digital_signature_present = bool(
            getattr(digital_signature, "has_signature", False)
            or getattr(digital_signature, "is_signed", False)
            or getattr(digital_signature, "signatures_count", 0)
        )

        header_valid = getattr(pdf_structure, "header_valid", None)
        eof_valid = getattr(pdf_structure, "eof_valid", None)
        multiple_eof = getattr(pdf_structure, "eof_count", 0) > 1
        encrypted = getattr(pdf_structure, "encrypted", None)
        javascript_detected = getattr(pdf_structure, "javascript_detected", None)
        embedded_files = getattr(pdf_structure, "embedded_files", None)
        xref_valid = getattr(pdf_structure, "xref_found", None)
        trailer_valid = getattr(pdf_structure, "trailer_found", None)
        incremental_updates = getattr(pdf_structure, "incremental_updates", None)

        is_structurally_valid = bool(
            magic_number_verified
            and header_valid
            and eof_valid
            and xref_valid
            and trailer_valid
        )

        score = 100

        if not hash_verified:
            score -= 20

        if not magic_number_verified:
            score -= 20

        if not header_valid:
            score -= 15

        if not eof_valid:
            score -= 15

        if not xref_valid:
            score -= 10

        if not trailer_valid:
            score -= 10

        if javascript_detected:
            score -= 10

        if embedded_files:
            score -= 10

        if encrypted:
            score -= 5

        if not digital_signature_present:
            score -= 5

        score = max(0, min(100, score))

        technical_status = (
            "Integridade estrutural básica verificada"
            if score >= 80
            else "Integridade estrutural com pontos de atenção"
        )

        return IntegrityResult(
            score=score,
            technical_status=technical_status,
            is_structurally_valid=is_structurally_valid,
            hash_verified=hash_verified,
            magic_number_verified=magic_number_verified,
            digital_signature_present=digital_signature_present,
            header_valid=header_valid,
            eof_valid=eof_valid,
            multiple_eof=multiple_eof,
            encrypted=encrypted,
            javascript_detected=javascript_detected,
            embedded_files=embedded_files,
            xref_valid=xref_valid,
            trailer_valid=trailer_valid,
            incremental_updates=incremental_updates,
        )
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
from app.models.json_analysis_result import JsonAnalysisResult
from app.services.json_parser_service import JsonParserService


class FileAnalyzer:
    """
    Coordena a análise técnica completa de um arquivo.

    O processamento especializado de JSON é encaminhado ao
    núcleo Rust através do JsonParserService.
    """

    JSON_EXTENSIONS = {
        ".json",
        ".jsonl",
        ".ndjson",
    }

    def __init__(
        self,
        hash_engine: HashEngine,
        metadata_engine: MetadataEngine,
        findings_engine: FindingsEngine,
        magic_number_engine: MagicNumberEngine,
        digital_signature_engine: DigitalSignatureEngine,
        pdf_structure_engine: PDFStructureEngine,
        json_parser_service: JsonParserService | None = None,
    ) -> None:
        self.hash_engine = hash_engine
        self.metadata_engine = metadata_engine
        self.findings_engine = findings_engine
        self.magic_number_engine = magic_number_engine
        self.digital_signature_engine = digital_signature_engine
        self.pdf_structure_engine = pdf_structure_engine

        self.json_parser_service = (
            json_parser_service
            if json_parser_service is not None
            else JsonParserService()
        )

    def analyze(
        self,
        file_path: Path,
    ) -> AnalysisResult:
        file_path = Path(file_path)
        stat = file_path.stat()

        file_info = FileInfo(
            name=file_path.name,
            path=file_path,
            extension=file_path.suffix.lower(),
            size_bytes=stat.st_size,
            created_at=datetime.fromtimestamp(
                stat.st_ctime
            ),
            modified_at=datetime.fromtimestamp(
                stat.st_mtime
            ),
            accessed_at=datetime.fromtimestamp(
                stat.st_atime
            ),
        )

        hashes = self.hash_engine.calculate_all(
            file_path
        )

        metadata = self.metadata_engine.extract(
            file_path
        )

        magic_numbers = (
            self.magic_number_engine.analyze(
                file_path
            )
        )

        digital_signature = (
            self.digital_signature_engine.analyze(
                file_path
            )
        )

        pdf_structure = None

        if magic_numbers.detected_format == "PDF":
            pdf_structure = (
                self.pdf_structure_engine.analyze(
                    file_path
                )
            )

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

        json_analysis = self._analyze_json(
            file_path
        )

        return AnalysisResult(
            file_info=file_info,
            hashes=hashes,
            metadata=metadata,
            findings=findings,
            magic_numbers=magic_numbers,
            digital_signature=digital_signature,
            integrity=integrity,
            json_analysis=json_analysis,
        )

    def _analyze_json(
        self,
        file_path: Path,
    ) -> JsonAnalysisResult | None:
        if (
            file_path.suffix.lower()
            not in self.JSON_EXTENSIONS
        ):
            return None

        try:
            return self.json_parser_service.parse(
                file_path
            )

        except Exception as error:
            return JsonAnalysisResult(
                is_valid=False,
                error_message=str(error),
            )

    def _build_integrity_result(
        self,
        hashes,
        magic_numbers,
        digital_signature,
        pdf_structure,
    ) -> IntegrityResult:
        hash_verified = bool(
            getattr(
                hashes,
                "sha256",
                None,
            )
        )

        magic_number_verified = (
            magic_numbers.extension_matches
        )

        digital_signature_present = (
            digital_signature.has_signature
        )
        digital_signature_analysis_status = getattr(
            digital_signature,
            "analysis_status",
            None,
        )
        digital_signature_error = getattr(
            digital_signature,
            "error_message",
            None,
        )

        pdf_structure_applicable = (
            pdf_structure is not None
        )

        if pdf_structure_applicable:
            header_valid = pdf_structure.header_valid
            eof_valid = pdf_structure.eof_valid
            multiple_eof = (
                pdf_structure.eof_count > 1
            )
            encrypted = pdf_structure.encrypted
            javascript_detected = (
                pdf_structure.javascript_detected
            )
            embedded_files = (
                pdf_structure.embedded_files
            )
            xref_valid = pdf_structure.xref_found
            trailer_valid = pdf_structure.trailer_found
            incremental_updates = (
                pdf_structure.incremental_updates
            )
            is_structurally_valid = bool(
                magic_number_verified
                and header_valid
                and eof_valid
                and xref_valid
                and trailer_valid
            )
        else:
            header_valid = None
            eof_valid = None
            multiple_eof = None
            encrypted = None
            javascript_detected = None
            embedded_files = None
            xref_valid = None
            trailer_valid = None
            incremental_updates = None
            is_structurally_valid = None

        score = 100

        if not hash_verified:
            score -= 20

        if not magic_number_verified:
            score -= 20

        if pdf_structure_applicable:
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

        if digital_signature_present is False:
            score -= 5

        score = max(
            0,
            min(100, score),
        )

        technical_status = (
            "Verificações técnicas registradas individualmente; "
            "consulte os estados de cada análise."
        )

        return IntegrityResult(
            score=score,
            technical_status=technical_status,
            is_structurally_valid=is_structurally_valid,
            hash_verified=hash_verified,
            magic_number_verified=magic_number_verified,
            digital_signature_present=(
                digital_signature_present
            ),
            digital_signature_analysis_status=(
                digital_signature_analysis_status
            ),
            digital_signature_error=(
                digital_signature_error
            ),
            header_valid=header_valid,
            eof_valid=eof_valid,
            multiple_eof=multiple_eof,
            encrypted=encrypted,
            javascript_detected=(
                javascript_detected
            ),
            embedded_files=embedded_files,
            xref_valid=xref_valid,
            trailer_valid=trailer_valid,
            incremental_updates=(
                incremental_updates
            ),
        )

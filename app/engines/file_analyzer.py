from datetime import datetime, timezone
from pathlib import Path

from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.finding_engine import FindingsEngine
from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.metadata_engine import MetadataEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.models import AnalysisResult, FileInfo, MetadataResult
from app.models.integrity_result import IntegrityResult
from app.models.json_analysis_result import JsonAnalysisResult
from app.models.biometric_report import BiometricReport
from app.services.json_parser_service import JsonParserService
from app.services.biometric_report_exceptions import (
    BiometricReportError,
    InvalidBiometricJsonError,
    UnrecognizedBiometricReportError,
)
from app.services.biometric_report_service import BiometricReportService
from app.engines.binary_structure_engine import BinaryStructureEngine
from app.processing import ProcessingIssue, ProcessingStatus, StepResult
from app.processing import ProcessingImpact
from app.evidence.models import CaptureState, EvidenceSource


class UnacquiredEvidenceError(RuntimeError):
    """Uso inseguro do agregador fora da fronteira de aquisição."""


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
        binary_structure_engine: BinaryStructureEngine | None = None,
        biometric_report_service: BiometricReportService | None = None,
    ) -> None:
        self.hash_engine = hash_engine
        self.metadata_engine = metadata_engine
        self.findings_engine = findings_engine
        self.magic_number_engine = magic_number_engine
        self.digital_signature_engine = digital_signature_engine
        self.pdf_structure_engine = pdf_structure_engine
        self.binary_structure_engine = binary_structure_engine
        self.biometric_report_service = biometric_report_service

        self.json_parser_service = (
            json_parser_service
            if json_parser_service is not None
            else JsonParserService()
        )

    def analyze(
        self,
        file_path: Path,
    ) -> AnalysisResult:
        """Bloqueia o uso acidental deste componente como entrada pública.

        Use ``AnalysisService.analyze`` para uma análise oficial ou
        ``analyze_fixture`` em testes unitários controlados.
        """
        raise UnacquiredEvidenceError(
            "FileAnalyzer não é uma fronteira pública. Use AnalysisService.analyze() "
            "ou analyze_fixture() apenas em testes unitários controlados."
        )

    def analyze_acquired(self, evidence: EvidenceSource) -> AnalysisResult:
        """Executa engines somente sobre a cópia criada pelo EvidenceManager."""
        if evidence.capture_state is not CaptureState.ACQUIRED:
            raise UnacquiredEvidenceError(
                "A evidência deve estar no estado ACQUIRED antes dos engines."
            )
        working_path = Path(evidence.working_path)
        if working_path == evidence.original_path or not working_path.is_file():
            raise UnacquiredEvidenceError("Cópia de trabalho adquirida inválida.")
        return self._analyze_path(working_path)

    def analyze_fixture(self, file_path: Path) -> AnalysisResult:
        """Entrada explícita para testes unitários de engines com fixture controlada."""
        return self._analyze_path(Path(file_path))

    def _analyze_path(
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
                stat.st_ctime, tz=timezone.utc
            ),
            modified_at=datetime.fromtimestamp(
                stat.st_mtime, tz=timezone.utc
            ),
            accessed_at=datetime.fromtimestamp(
                stat.st_atime, tz=timezone.utc
            ),
        )

        hashes = self.hash_engine.calculate_all(
            file_path
        )

        processing_steps = []
        extract_step = getattr(self.metadata_engine, "extract_step", None)
        if callable(extract_step):
            metadata_step = extract_step(file_path)
            processing_steps.append(metadata_step)
            metadata = metadata_step.value or MetadataResult(raw={})
        else:
            metadata = self.metadata_engine.extract(file_path)

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
            try:
                pdf_structure = self.pdf_structure_engine.analyze(file_path)
                processing_steps.append(
                    self._processing_step(
                        "pdf_structure",
                        "pdf_structure",
                        ProcessingStatus.SUCCESS,
                        "Estrutura PDF analisada.",
                        value=pdf_structure,
                    )
                )
            except Exception as error:
                issue = self._processing_issue(
                    "pdf_structure_failed",
                    "pdf_structure",
                    ProcessingStatus.FAILED,
                    "A estrutura PDF não pôde ser analisada.",
                    error,
                )
                processing_steps.append(
                    self._processing_step(
                        "pdf_structure",
                        "pdf_structure",
                        ProcessingStatus.FAILED,
                        issue.user_message,
                        issues=[issue],
                    )
                )
        else:
            processing_steps.append(
                self._processing_step(
                    "pdf_structure",
                    "pdf_structure",
                    ProcessingStatus.SKIPPED,
                    "Formato não aplicável à análise de estrutura PDF.",
                )
            )

        integrity = self._build_integrity_result(
            hashes=hashes,
            magic_numbers=magic_numbers,
            digital_signature=digital_signature,
            pdf_structure=pdf_structure,
        )

        json_step = self._analyze_json(
            file_path
        )
        processing_steps.append(json_step)
        json_analysis = json_step.value

        biometric_step = self._analyze_biometric_report(file_path)
        processing_steps.append(biometric_step)
        biometric_report = biometric_step.value

        findings = self.findings_engine.analyze(
            metadata=metadata,
            integrity=integrity,
            biometric_report=biometric_report,
        )

        binary_analysis = None
        if self.binary_structure_engine is not None:
            try:
                binary_analysis = self.binary_structure_engine.analyze(file_path)
                if binary_analysis is not None:
                    processing_steps.extend(binary_analysis.processing_steps)
            except Exception as error:
                issue = ProcessingIssue(
                    code="binary_analysis_failed",
                    status=ProcessingStatus.FAILED,
                    technical_message=(
                        "A análise binária falhou antes de produzir resultado."
                    ),
                    user_message="A análise binária não pôde ser concluída.",
                    component="binary",
                    details={"error_type": type(error).__name__},
                    original_exception=error,
                )
                processing_steps.append(
                    StepResult(
                        code="binary_analysis",
                        component="binary",
                        status=ProcessingStatus.FAILED,
                        technical_message=issue.technical_message,
                        user_message=issue.user_message,
                        issues=[issue],
                    )
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
            binary_analysis=binary_analysis,
            pdf_structure=pdf_structure,
            biometric_report=biometric_report,
            processing_steps=processing_steps,
        )

    def _analyze_biometric_report(
        self,
        file_path: Path,
    ) -> StepResult[BiometricReport]:
        if (
            file_path.suffix.lower() != ".json"
        ):
            return self._processing_step(
                "biometric_analysis",
                "biometric",
                ProcessingStatus.SKIPPED,
                "Formato não aplicável à análise biométrica.",
            )
        if self.biometric_report_service is None:
            issue = self._processing_issue(
                "biometric_parser_unavailable",
                "biometric",
                ProcessingStatus.UNAVAILABLE,
                "Parser biométrico não configurado.",
            )
            return self._processing_step(
                "biometric_analysis",
                "biometric",
                ProcessingStatus.UNAVAILABLE,
                issue.user_message,
                issues=[issue],
            )
        try:
            report = self.biometric_report_service.parse(file_path)
            if report is None:
                return self._processing_step(
                    "biometric_analysis", "biometric", ProcessingStatus.NO_FINDINGS,
                    "Nenhuma estrutura biométrica reconhecida.",
                )
            status = ProcessingStatus.PARTIAL if report.warnings else ProcessingStatus.SUCCESS
            return self._processing_step(
                "biometric_analysis", "biometric", status,
                "Relatório biométrico interpretado.", value=report,
            )
        except UnrecognizedBiometricReportError:
            return self._processing_step(
                "biometric_analysis", "biometric", ProcessingStatus.NO_FINDINGS,
                "JSON válido sem estrutura biométrica reconhecida.",
            )
        except InvalidBiometricJsonError as error:
            issue = self._processing_issue(
                "biometric_json_invalid", "biometric", ProcessingStatus.FAILED,
                "O JSON não pôde ser validado para análise biométrica.", error,
            )
            return self._processing_step(
                "biometric_analysis", "biometric", ProcessingStatus.FAILED,
                issue.user_message, issues=[issue],
            )
        except BiometricReportError as error:
            issue = self._processing_issue(
                "biometric_parser_failed", "biometric", ProcessingStatus.FAILED,
                "O parser biométrico não concluiu a análise.", error,
            )
            return self._processing_step(
                "biometric_analysis", "biometric", ProcessingStatus.FAILED,
                issue.user_message, issues=[issue],
            )

    def _analyze_json(
        self,
        file_path: Path,
    ) -> StepResult[JsonAnalysisResult]:
        if (
            file_path.suffix.lower()
            not in self.JSON_EXTENSIONS
        ):
            return self._processing_step(
                "json_analysis", "json", ProcessingStatus.SKIPPED,
                "Formato não aplicável à análise JSON.",
            )

        parse_step = getattr(self.json_parser_service, "parse_step", None)
        if callable(parse_step):
            return parse_step(file_path)
        try:
            value = self.json_parser_service.parse(file_path)
        except Exception as error:
            issue = self._processing_issue(
                "json_parser_failed", "json", ProcessingStatus.FAILED,
                "O parser JSON não concluiu a análise.", error,
            )
            return self._processing_step(
                "json_analysis", "json", ProcessingStatus.FAILED,
                issue.user_message,
                value=JsonAnalysisResult(is_valid=False, error_message=issue.user_message),
                issues=[issue],
            )
        status = ProcessingStatus.SUCCESS if value.is_valid else ProcessingStatus.FAILED
        return self._processing_step(
            "json_analysis", "json", status,
            "Análise JSON concluída." if value.is_valid else "JSON inválido.",
            value=value,
        )

    @staticmethod
    def _processing_issue(
        code: str,
        component: str,
        status: ProcessingStatus,
        message: str,
        error: BaseException | None = None,
    ) -> ProcessingIssue:
        return ProcessingIssue(
            code=code,
            component=component,
            status=status,
            technical_message=message,
            user_message=message,
            impact=ProcessingImpact.COMPONENT_ONLY,
            details={"error_type": type(error).__name__} if error else {},
            original_exception=error,
        )

    @staticmethod
    def _processing_step(
        code: str,
        component: str,
        status: ProcessingStatus,
        message: str,
        *,
        value=None,
        issues: list[ProcessingIssue] | None = None,
    ) -> StepResult:
        return StepResult(
            code=code,
            component=component,
            status=status,
            technical_message=message,
            user_message=message,
            value=value,
            issues=issues or [],
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
            # Esta etapa observa marcadores, mas não executa validação completa.
            # Xref streams, revisões incrementais e reparos legítimos tornam uma
            # conclusão booleana baseada nesses marcadores tecnicamente indevida.
            is_structurally_valid = None
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

        technical_status = (
            "Score agregado desativado; consulte separadamente hash, tipo real, "
            "estrutura observada, assinatura, metadados e limitações."
        )

        return IntegrityResult(
            score=None,
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

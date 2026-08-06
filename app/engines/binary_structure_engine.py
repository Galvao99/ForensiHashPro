from pathlib import Path
from typing import Protocol

from app.binary import (
    BinaryReader,
    BinaryStringExtractor,
    EntropyAnalyzer,
    SignatureScanner,
)
from app.binary.parsers import PdfRawParser
from app.binary.signatures import BINARY_SIGNATURES
from app.models.binary_analysis_result import BinaryAnalysisResult
from app.models.binary_finding import BinaryFinding
from app.processing import (
    ProcessingIssue,
    ProcessingLimitExceededError,
    ProcessingStatus,
    StepResult,
)


class _Scanner(Protocol):
    def scan(self, reader: BinaryReader, max_results_per_signature: int): ...


class _StringExtractor(Protocol):
    def extract(self, reader: BinaryReader): ...


class _EntropyAnalyzer(Protocol):
    def analyze(self, reader: BinaryReader): ...

    def weighted_average(self, regions): ...


class _PdfRawParser(Protocol):
    def analyze(self, reader: BinaryReader): ...


class BinaryStructureEngine:
    """Coordinates bounded binary analyses without format interpretation."""

    def __init__(
        self,
        *,
        header_size: int = 256,
        footer_size: int = 256,
        signature_max_results: int = 100,
        string_minimum_length: int = 4,
        string_maximum_results: int = 1000,
        string_chunk_size: int = 64 * 1024,
        entropy_block_size: int = 64 * 1024,
        signature_scanner: _Scanner | None = None,
        string_extractor: _StringExtractor | None = None,
        entropy_analyzer: _EntropyAnalyzer | None = None,
        pdf_raw_parser: _PdfRawParser | None = None,
    ) -> None:
        if header_size < 0 or footer_size < 0:
            raise ValueError("header and footer sizes must not be negative")
        if signature_max_results <= 0:
            raise ValueError("signature_max_results must be greater than zero")
        self.header_size = header_size
        self.footer_size = footer_size
        self.signature_max_results = signature_max_results
        self.signature_scanner = signature_scanner or SignatureScanner()
        self.string_extractor = string_extractor or BinaryStringExtractor(
            minimum_length=string_minimum_length,
            maximum_results=string_maximum_results,
            chunk_size=string_chunk_size,
        )
        self.entropy_analyzer = entropy_analyzer or EntropyAnalyzer(
            block_size=entropy_block_size
        )
        self.pdf_raw_parser = pdf_raw_parser or PdfRawParser()

    def analyze(self, file_path: Path) -> BinaryAnalysisResult:
        reader = BinaryReader(Path(file_path))
        result = BinaryAnalysisResult(
            file_size=reader.size,
            header_bytes=reader.read_header(self.header_size),
            footer_bytes=reader.read_footer(self.footer_size),
        )
        self._run_component(
            result,
            "signature_scan_failed",
            "Falha no scanner de assinaturas",
            lambda: setattr(
                result,
                "regions",
                self.signature_scanner.scan(
                    reader, self.signature_max_results
                ),
            ),
            output=lambda: result.regions,
        )
        self._run_component(
            result,
            "string_extraction_failed",
            "Falha na extração de strings",
            lambda: setattr(
                result, "strings", self.string_extractor.extract(reader)
            ),
            output=lambda: result.strings,
            limit=getattr(self.string_extractor, "maximum_results", None),
        )
        self._run_component(
            result,
            "entropy_analysis_failed",
            "Falha na análise de entropia",
            lambda: self._set_entropy(result, reader),
            output=lambda: result.entropy_regions,
        )
        if self._is_pdf(reader):
            self._run_component(
                result,
                "pdf_raw_parser_failed",
                "Falha no parser estrutural de PDF",
                lambda: self._set_pdf_raw_analysis(result, reader),
                output=lambda: result.pdf_raw_analysis,
            )
        else:
            result.processing_steps.append(
                StepResult(
                    code="binary_pdf_parser",
                    component="binary.pdf_raw",
                    status=ProcessingStatus.SKIPPED,
                    technical_message="O parser PDF bruto não se aplica ao formato.",
                    user_message="A etapa estrutural PDF não se aplica a este arquivo.",
                )
            )
        return result

    @staticmethod
    def _is_pdf(reader: BinaryReader) -> bool:
        signature = BINARY_SIGNATURES["pdf"] + b"-"
        return bool(
            reader.find_bytes(
                signature,
                end=min(reader.size, PdfRawParser.HEADER_LIMIT),
                max_results=1,
            )
        )

    def _set_pdf_raw_analysis(
        self, result: BinaryAnalysisResult, reader: BinaryReader
    ) -> None:
        analysis = self.pdf_raw_parser.analyze(reader)
        result.pdf_raw_analysis = analysis
        result.parser_name = "pdf_raw"
        result.findings.extend(analysis.findings)

    def _set_entropy(
        self, result: BinaryAnalysisResult, reader: BinaryReader
    ) -> None:
        regions = self.entropy_analyzer.analyze(reader)
        result.entropy_regions = regions
        result.average_entropy = self.entropy_analyzer.weighted_average(regions)

    @staticmethod
    def _run_component(
        result: BinaryAnalysisResult,
        code: str,
        title: str,
        operation,
        output,
        limit: int | None = None,
    ) -> None:
        try:
            operation()
            value = output()
            status = ProcessingStatus.SUCCESS
            message = "Componente concluído com sucesso."
            if value is None or (hasattr(value, "__len__") and len(value) == 0):
                status = ProcessingStatus.NO_FINDINGS
                message = "Componente concluído sem resultados."
            issues: list[ProcessingIssue] = []
            if limit is not None and hasattr(value, "__len__") and len(value) >= limit:
                status = ProcessingStatus.PARTIAL
                message = "O limite de resultados foi atingido; dados parciais preservados."
                issues.append(
                    ProcessingIssue(
                        code=f"{code.removesuffix('_failed')}_limit",
                        status=ProcessingStatus.PARTIAL,
                        technical_message=message,
                        user_message=message,
                        component=f"binary.{code.removesuffix('_failed')}",
                        details={"limit": limit, "preserved": len(value)},
                    )
                )
            result.processing_steps.append(
                StepResult(
                    code=code.removesuffix("_failed"),
                    component=f"binary.{code.removesuffix('_failed')}",
                    status=status,
                    technical_message=message,
                    user_message=message,
                    issues=issues,
                )
            )
        except Exception as error:
            failure_status = (
                ProcessingStatus.LIMIT_EXCEEDED
                if isinstance(error, ProcessingLimitExceededError)
                else ProcessingStatus.FAILED
            )
            issue = ProcessingIssue(
                code=code,
                status=failure_status,
                technical_message=f"{title}: {type(error).__name__}",
                user_message=(
                    "O componente binário falhou; resultados de outros componentes "
                    "foram preservados."
                ),
                component=f"binary.{code.removesuffix('_failed')}",
                details={"error_type": type(error).__name__},
                original_exception=error,
            )
            result.processing_steps.append(
                StepResult(
                    code=code.removesuffix("_failed"),
                    component=issue.component,
                    status=failure_status,
                    technical_message=issue.technical_message,
                    user_message=issue.user_message,
                    issues=[issue],
                )
            )
            result.findings.append(
                BinaryFinding(
                    code=code,
                    title=title,
                    description=(
                        "O componente não pôde concluir sua etapa; "
                        "os demais resultados binários foram preservados."
                    ),
                    evidence={"error_type": type(error).__name__},
                )
            )

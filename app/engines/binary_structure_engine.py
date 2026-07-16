from pathlib import Path
from typing import Protocol

from app.binary import (
    BinaryReader,
    BinaryStringExtractor,
    EntropyAnalyzer,
    SignatureScanner,
)
from app.models.binary_analysis_result import BinaryAnalysisResult
from app.models.binary_finding import BinaryFinding


class _Scanner(Protocol):
    def scan(self, reader: BinaryReader, max_results_per_signature: int): ...


class _StringExtractor(Protocol):
    def extract(self, reader: BinaryReader): ...


class _EntropyAnalyzer(Protocol):
    def analyze(self, reader: BinaryReader): ...

    def weighted_average(self, regions): ...


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
        )
        self._run_component(
            result,
            "string_extraction_failed",
            "Falha na extração de strings",
            lambda: setattr(
                result, "strings", self.string_extractor.extract(reader)
            ),
        )
        self._run_component(
            result,
            "entropy_analysis_failed",
            "Falha na análise de entropia",
            lambda: self._set_entropy(result, reader),
        )
        return result

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
    ) -> None:
        try:
            operation()
        except Exception as error:
            result.findings.append(
                BinaryFinding(
                    code=code,
                    title=title,
                    description=(
                        "O componente não pôde concluir sua etapa; "
                        "os demais resultados binários foram preservados."
                    ),
                    evidence={"error_type": type(error).__name__, "message": str(error)},
                )
            )

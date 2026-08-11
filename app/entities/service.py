from __future__ import annotations

from collections.abc import Iterable

from app.entities.candidate_extractor import CandidateExtractor
from app.entities.models import (
    EntityCandidate,
    EntityResolutionResult,
    EntitySourceType,
)
from app.entities.resolver import EntityResolver
from app.models import AnalysisResult
from app.services.text_extraction_service import TextExtractionResult


class EntityExtractionService:
    """Fachada do domínio para fontes textuais e estruturadas já extraídas."""

    def __init__(
        self,
        *,
        candidate_extractor: CandidateExtractor | None = None,
        resolver: EntityResolver | None = None,
    ) -> None:
        self.candidate_extractor = candidate_extractor or CandidateExtractor()
        self.resolver = resolver or EntityResolver()

    def resolve_analysis(
        self,
        result: AnalysisResult,
        *,
        text_result: TextExtractionResult | None = None,
    ) -> EntityResolutionResult:
        source_file = str(result.file_info.path.resolve())
        candidates: list[EntityCandidate] = []

        if text_result is not None and text_result.segments:
            for segment in text_result.segments:
                candidates.extend(
                    self.candidate_extractor.extract_text(
                        segment.text,
                        source_type=self._source_type(segment.source),
                        source_file=source_file,
                        page=segment.page,
                        extractor="text_extraction_service",
                    )
                )
        elif result.extracted_text:
            source = self._source_type(text_result.source if text_result else "legacy_text")
            candidates.extend(
                self.candidate_extractor.extract_text(
                    result.extracted_text,
                    source_type=source,
                    source_file=source_file,
                    extractor="analysis_result_legacy_text",
                )
            )

        candidates.extend(self._metadata_candidates(result, source_file))
        candidates.extend(self._json_candidates(result, source_file))
        return self.resolver.resolve(candidates)

    def resolve_legacy_text(self, text: str, *, source_file: str) -> EntityResolutionResult:
        return self.resolver.resolve(
            self.candidate_extractor.extract_text(
                text,
                source_type=EntitySourceType.LEGACY_TEXT,
                source_file=source_file,
                extractor="investigation_context_legacy_adapter",
            )
        )

    def _metadata_candidates(
        self, result: AnalysisResult, source_file: str
    ) -> Iterable[EntityCandidate]:
        for key, value in result.metadata.raw.items():
            candidate = self.candidate_extractor.extract_structured(
                value,
                source_type=EntitySourceType.METADATA,
                source_file=source_file,
                field_path=str(key),
                extractor="metadata_field",
            )
            if candidate is not None and (
                candidate.initial_hints != ("structured_field",)
                or any(marker in candidate.raw_value for marker in ("@", "R$", ":"))
            ):
                yield candidate

    def _json_candidates(
        self, result: AnalysisResult, source_file: str
    ) -> Iterable[EntityCandidate]:
        if result.json_analysis is None:
            return
        for field in result.json_analysis.fields:
            candidate = self.candidate_extractor.extract_structured(
                field.value,
                source_type=EntitySourceType.JSON,
                source_file=source_file,
                field_path=field.path,
                extractor="rust_json_field",
            )
            if candidate is not None:
                yield candidate

    @staticmethod
    def _source_type(value: str) -> EntitySourceType:
        return {
            "native": EntitySourceType.NATIVE_TEXT,
            "native_text": EntitySourceType.NATIVE_TEXT,
            "native_partial": EntitySourceType.NATIVE_TEXT,
            "ocr": EntitySourceType.OCR,
            "legacy_text": EntitySourceType.LEGACY_TEXT,
        }.get(value, EntitySourceType.LEGACY_TEXT)

from __future__ import annotations

import importlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import fitz

from app.processing import (
    ProcessingImpact,
    ProcessingIssue,
    ProcessingStatus,
    StepResult,
)
from app.settings.processing_limits import ProcessingLimits
from app.settings.tooling import ToolDetector, ToolStatus, ToolUnavailableError


@dataclass(slots=True)
class TextSegment:
    text: str
    source: str
    page: int | None = None


@dataclass(slots=True)
class TextExtractionResult:
    text: str = ""
    source: str = "none"
    pages_processed: int = 0
    total_pages: int | None = None
    issues: list[ProcessingIssue] = field(default_factory=list)
    segments: list[TextSegment] = field(default_factory=list)


class TextExtractionService:
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".bmp"}

    def __init__(
        self,
        *,
        tesseract_status: ToolStatus | None = None,
        poppler_status: ToolStatus | None = None,
        limits: ProcessingLimits | None = None,
    ) -> None:
        detector = ToolDetector()
        self.tesseract_status = tesseract_status or detector.tesseract()
        self.poppler_status = poppler_status or detector.poppler()
        self.limits = limits or ProcessingLimits()

    def extract_text(self, file_path: str | Path) -> str:
        """Adaptador legado: consumidores novos devem usar ``extract``."""
        return self.extract(file_path).value.text

    def extract(self, file_path: str | Path) -> StepResult[TextExtractionResult]:
        path = Path(file_path)
        started = datetime.now(timezone.utc)
        if path.suffix.lower() == ".pdf":
            return self._extract_pdf(path, started)
        if path.suffix.lower() in self.IMAGE_EXTENSIONS:
            return self._extract_image(path, started)
        return self._step(
            started,
            ProcessingStatus.SKIPPED,
            "Formato sem extração textual configurada.",
            "A extração textual não se aplica a este formato.",
            TextExtractionResult(source="unsupported"),
        )

    def _extract_pdf(
        self, path: Path, started: datetime
    ) -> StepResult[TextExtractionResult]:
        issues: list[ProcessingIssue] = []
        native_parts: list[str] = []
        native_segments: list[TextSegment] = []
        try:
            with fitz.open(path) as document:
                total_pages = document.page_count
                if total_pages == 0:
                    return self._step(
                        started,
                        ProcessingStatus.NO_FINDINGS,
                        "PDF sem páginas renderizáveis.",
                        "O PDF não contém páginas renderizáveis.",
                        TextExtractionResult(source="native", total_pages=0),
                    )
                if total_pages > self.limits.max_pdf_pages:
                    return self._limit_step(
                        started,
                        "ocr_pdf_page_limit",
                        "O PDF excede o número máximo de páginas.",
                        {"pages": total_pages, "limit": self.limits.max_pdf_pages},
                    )
                for page_number, page in enumerate(document, start=1):
                    page_text = page.get_text("text") or ""
                    native_parts.append(page_text)
                    if page_text.strip():
                        native_segments.append(TextSegment(page_text.strip(), "native_text", page_number))
        except Exception as error:
            return self._failed_step(
                started,
                "pdf_native_extraction_failed",
                "A estrutura do PDF não pôde ser aberta para extração textual.",
                error,
            )

        native_text = "\n".join(native_parts).strip()
        if len(native_text) >= 80:
            return self._step(
                started,
                ProcessingStatus.SUCCESS,
                "Texto nativo extraído do PDF.",
                "Texto nativo extraído com sucesso.",
                TextExtractionResult(
                    text=native_text,
                    source="native",
                    pages_processed=total_pages,
                    total_pages=total_pages,
                    segments=native_segments,
                ),
            )

        unavailable = self._ocr_unavailable(
            started, native_text, total_pages, native_segments
        )
        if unavailable is not None:
            return unavailable

        result = TextExtractionResult(
            text=native_text,
            source="ocr",
            total_pages=total_pages,
            issues=issues,
            segments=list(native_segments),
        )
        started_clock = time.monotonic()
        for page_number in range(1, total_pages + 1):
            remaining = self.limits.ocr_timeout_seconds - (
                time.monotonic() - started_clock
            )
            if remaining <= 0:
                result.issues.append(
                    self._issue(
                        "ocr_timeout",
                        ProcessingStatus.PARTIAL if result.text else ProcessingStatus.FAILED,
                        "Tempo total de OCR excedido.",
                        "O OCR excedeu o tempo máximo configurado.",
                        {"page": page_number},
                    )
                )
                break
            try:
                pdf2image = importlib.import_module("pdf2image")
                pages = pdf2image.convert_from_path(
                    str(path),
                    dpi=300,
                    first_page=page_number,
                    last_page=page_number,
                    poppler_path=str(self.poppler_status.path)
                    if self.poppler_status.path
                    else None,
                    timeout=max(1, int(remaining)),
                )
                if not pages:
                    raise RuntimeError("A página não foi renderizada.")
                self._validate_image_size(pages[0])
                page_text = self._image_to_string(
                    pages[0], timeout=max(1, int(remaining))
                ).strip()
                if page_text:
                    result.text = "\n".join(
                        part for part in (result.text, page_text) if part
                    )
                    result.segments.append(TextSegment(page_text, "ocr", page_number))
                result.pages_processed += 1
            except Exception as error:
                result.issues.append(
                    self._issue(
                        "ocr_page_failed",
                        ProcessingStatus.PARTIAL,
                        f"Falha no OCR da página {page_number}.",
                        f"O OCR não conseguiu processar a página {page_number}.",
                        {"page": page_number, "error_type": type(error).__name__},
                        error,
                    )
                )

        if result.issues:
            status = ProcessingStatus.PARTIAL if result.text else ProcessingStatus.FAILED
            return self._step(
                started,
                status,
                "OCR concluído parcialmente." if result.text else "OCR falhou.",
                "Parte do texto foi preservada após falha de OCR."
                if result.text
                else "Não foi possível extrair texto por OCR.",
                result,
                result.issues,
            )
        status = ProcessingStatus.SUCCESS if result.text.strip() else ProcessingStatus.NO_FINDINGS
        return self._step(
            started,
            status,
            "OCR concluído.",
            "OCR concluído com sucesso."
            if result.text.strip()
            else "O OCR foi executado corretamente e nenhum texto foi identificado.",
            result,
        )

    def _extract_image(
        self, path: Path, started: datetime
    ) -> StepResult[TextExtractionResult]:
        if not self.tesseract_status.available:
            return self._unavailable_step(started, self.tesseract_status)
        try:
            pillow = importlib.import_module("PIL.Image")
            with pillow.open(path) as image:
                self._validate_image_size(image)
                text = self._image_to_string(
                    image, timeout=self.limits.ocr_timeout_seconds
                ).strip()
        except ValueError as error:
            return self._limit_step(
                started,
                "ocr_image_limit",
                str(error),
                {},
                error,
            )
        except Exception as error:
            return self._failed_step(
                started, "ocr_image_failed", "Falha ao processar a imagem por OCR.", error
            )
        status = ProcessingStatus.SUCCESS if text else ProcessingStatus.NO_FINDINGS
        return self._step(
            started,
            status,
            "OCR de imagem concluído.",
            "Texto extraído com sucesso."
            if text
            else "O OCR foi executado corretamente e nenhum texto foi identificado.",
            TextExtractionResult(
                text=text,
                source="ocr",
                pages_processed=1,
                segments=[TextSegment(text, "ocr", 1)] if text else [],
            ),
        )

    def _ocr_unavailable(
        self,
        started: datetime,
        native_text: str,
        total_pages: int,
        native_segments: list[TextSegment],
    ) -> StepResult[TextExtractionResult] | None:
        for status in (self.tesseract_status, self.poppler_status):
            if not status.available:
                step = self._unavailable_step(started, status)
                step.value.text = native_text
                step.value.source = "native_partial" if native_text else "unavailable"
                step.value.total_pages = total_pages
                step.value.segments = list(native_segments)
                if native_text:
                    step.status = ProcessingStatus.PARTIAL
                    step.user_message += " O texto nativo parcial foi preservado."
                return step
        return None

    def _image_to_string(self, image: object, *, timeout: int | None = None) -> str:
        self._require(self.tesseract_status)
        try:
            pytesseract = importlib.import_module("pytesseract")
        except (ImportError, ModuleNotFoundError) as error:
            raise RuntimeError("pytesseract não está instalado.") from error
        if self.tesseract_status.path is not None:
            pytesseract.pytesseract.tesseract_cmd = str(self.tesseract_status.path)
        effective_timeout = timeout or self.limits.ocr_timeout_seconds
        return str(
            pytesseract.image_to_string(
                image, lang="por", timeout=effective_timeout
            )
        )

    def _validate_image_size(self, image: object) -> None:
        width, height = image.size
        if width > self.limits.max_image_width or height > self.limits.max_image_height:
            raise ValueError("A imagem excede as dimensões máximas configuradas.")
        if width * height > self.limits.max_image_pixels:
            raise ValueError("A imagem excede a quantidade máxima de pixels configurada.")
        if width * height * 4 > self.limits.max_estimated_memory_bytes:
            raise ValueError("A memória estimada para a imagem excede o limite configurado.")

    def _unavailable_step(
        self, started: datetime, status: ToolStatus
    ) -> StepResult[TextExtractionResult]:
        error = ToolUnavailableError(status)
        issue = self._issue(
            "ocr_tool_unavailable",
            ProcessingStatus.UNAVAILABLE,
            status.message,
            f"{status.name} não está disponível; a etapa de OCR não foi executada.",
            {"tool": status.name, "tool_state": status.state.value},
            error,
        )
        return self._step(
            started,
            ProcessingStatus.UNAVAILABLE,
            status.message,
            issue.user_message,
            TextExtractionResult(source="unavailable", issues=[issue]),
            [issue],
        )

    def _failed_step(
        self, started: datetime, code: str, message: str, error: BaseException
    ) -> StepResult[TextExtractionResult]:
        issue = self._issue(
            code,
            ProcessingStatus.FAILED,
            message,
            "A extração textual falhou durante o processamento.",
            {"error_type": type(error).__name__},
            error,
        )
        return self._step(
            started,
            ProcessingStatus.FAILED,
            message,
            issue.user_message,
            TextExtractionResult(source="failed", issues=[issue]),
            [issue],
        )

    def _limit_step(
        self,
        started: datetime,
        code: str,
        message: str,
        details: dict[str, object],
        error: BaseException | None = None,
    ) -> StepResult[TextExtractionResult]:
        issue = self._issue(
            code,
            ProcessingStatus.LIMIT_EXCEEDED,
            message,
            "A etapa de OCR não foi executada porque excedeu um limite de segurança.",
            details,
            error,
        )
        return self._step(
            started,
            ProcessingStatus.LIMIT_EXCEEDED,
            message,
            issue.user_message,
            TextExtractionResult(source="limit", issues=[issue]),
            [issue],
        )

    @staticmethod
    def _issue(
        code: str,
        status: ProcessingStatus,
        technical: str,
        user: str,
        details: dict[str, object],
        error: BaseException | None = None,
    ) -> ProcessingIssue:
        return ProcessingIssue(
            code=code,
            status=status,
            technical_message=technical,
            user_message=user,
            component="text_extraction",
            details=dict(details),
            impact=ProcessingImpact.ANALYSIS_PARTIAL,
            original_exception=error,
        )

    @staticmethod
    def _step(
        started: datetime,
        status: ProcessingStatus,
        technical: str,
        user: str,
        value: TextExtractionResult,
        issues: list[ProcessingIssue] | None = None,
    ) -> StepResult[TextExtractionResult]:
        return StepResult(
            code="text_extraction",
            component="text_extraction",
            status=status,
            technical_message=technical,
            user_message=user,
            value=value,
            issues=issues or [],
            started_at_utc=started,
            finished_at_utc=datetime.now(timezone.utc),
        )

    @staticmethod
    def _require(status: ToolStatus) -> None:
        if not status.available:
            raise ToolUnavailableError(status)

from __future__ import annotations

from app.models.binary_finding import BinaryFinding
from app.models.pdf_raw_analysis_result import (
    PdfRawAnalysisResult,
    PdfRawObject,
    PdfStartXref,
)


class PdfRawTechnicalFormatter:
    """Formata fatos estruturais existentes sem interpretá-los."""

    FEATURES = (
        ("JavaScript", "has_javascript"),
        ("Encrypt", "encrypted"),
        ("EmbeddedFile", "has_embedded_files"),
        ("OpenAction", "has_open_action"),
        ("Additional Actions", "has_additional_actions"),
        ("AcroForm", "has_acroform"),
        ("XFA", "has_xfa"),
    )

    def format(self, result: PdfRawAnalysisResult | None) -> str:
        if result is None:
            return "Nenhuma estrutura técnica disponível."

        sections = ["ESTRUTURA TÉCNICA DO PDF", "=" * 48]
        self._append_section(
            sections,
            "INFORMAÇÕES GERAIS",
            [
                self._pair("Versão", self._format_version(result.version)),
                self._pair(
                    "Offset do cabeçalho",
                    self._format_optional_offset(result.header_offset),
                ),
            ],
        )
        self._append_section(
            sections,
            "OBJETOS",
            [self._format_object(item) for item in result.objects]
            or ["Nenhum objeto registrado."],
        )
        self._append_section(
            sections,
            "STREAMS",
            [self._pair("Quantidade", str(result.stream_count))],
        )
        self._append_offsets(sections, "XREF", "xref", result.xref_offsets)
        self._append_offsets(
            sections,
            "XREF STREAMS",
            "xref stream",
            result.xref_stream_offsets,
        )
        self._append_offsets(
            sections,
            "TRAILERS",
            "trailer",
            result.trailer_offsets,
        )
        self._append_section(
            sections,
            "STARTXREF",
            [self._format_startxref(item) for item in result.startxrefs]
            or ["Nenhum registro."],
        )
        self._append_offsets(
            sections,
            "MARCADORES %%EOF",
            "%%EOF",
            result.eof_offsets,
        )
        self._append_offsets(
            sections,
            "REFERÊNCIAS /Prev",
            "/Prev",
            result.prev_offsets,
        )
        self._append_section(
            sections,
            "RECURSOS ANALISADOS",
            [
                self._pair(
                    label,
                    "detectado" if getattr(result, attribute) else "não detectado",
                )
                for label, attribute in self.FEATURES
            ],
        )
        self._append_section(
            sections,
            "FINDINGS ESTRUTURAIS",
            [self._format_finding(item) for item in result.findings]
            or ["Nenhum finding estrutural registrado."],
        )
        return "\n".join(sections).rstrip() + "\n"

    def _append_offsets(
        self,
        sections: list[str],
        title: str,
        label: str,
        offsets: list[int],
    ) -> None:
        lines = [
            f"{index:03d}. {label} @ {self._format_offset(offset)}"
            for index, offset in enumerate(offsets, start=1)
        ]
        self._append_section(sections, title, lines or ["Nenhum registro."])

    @staticmethod
    def _format_object(item: PdfRawObject) -> str:
        end = (
            PdfRawTechnicalFormatter._format_offset(item.end_offset)
            if item.end_offset is not None
            else "Não informado"
        )
        return (
            f"{item.object_number} {item.generation_number} obj | "
            f"início: {PdfRawTechnicalFormatter._format_offset(item.start_offset)} | "
            f"fim: {end} | stream: "
            f"{'sim' if item.has_stream else 'não'}"
        )

    @staticmethod
    def _format_startxref(item: PdfStartXref) -> str:
        declared = (
            PdfRawTechnicalFormatter._format_offset(item.declared_offset)
            if item.declared_offset is not None
            else "Não informado"
        )
        return (
            f"marcador @ {PdfRawTechnicalFormatter._format_offset(item.marker_offset)}"
            f" | offset declarado: {declared}"
        )

    @staticmethod
    def _format_finding(finding: BinaryFinding) -> str:
        offset = (
            f" | offset: {PdfRawTechnicalFormatter._format_offset(finding.offset)}"
            if finding.offset is not None
            else ""
        )
        return f"- {finding.title}: {finding.description}{offset}"

    @staticmethod
    def _append_section(
        sections: list[str],
        title: str,
        lines: list[str],
    ) -> None:
        sections.extend(("", title, "-" * len(title), *lines))

    @staticmethod
    def _pair(label: str, value: str) -> str:
        return f"{label:<24} {value}"

    @staticmethod
    def _format_version(value: str | None) -> str:
        if not value:
            return "Não informado"
        return value if value.upper().startswith("PDF") else f"PDF {value}"

    @staticmethod
    def _format_optional_offset(value: int | None) -> str:
        if value is None:
            return "Não informado"
        return PdfRawTechnicalFormatter._format_offset(value)

    @staticmethod
    def _format_offset(value: int) -> str:
        return f"{value} (0x{value:X})"

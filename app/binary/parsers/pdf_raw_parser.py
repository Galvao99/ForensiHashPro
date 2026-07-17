import mmap
import re
from collections.abc import Iterator

from app.binary.binary_reader import BinaryReader
from app.binary.signatures import BINARY_SIGNATURES
from app.models.binary_finding import BinaryFinding
from app.models.pdf_raw_analysis_result import (
    PdfRawAnalysisResult,
    PdfRawObject,
    PdfStartXref,
)


class PdfRawParser:
    """Locates observable PDF structures without rendering or decoding streams."""

    HEADER_LIMIT = 1024
    _OBJECT = re.compile(rb"(?m)(?<!\d)(\d+)[\x00\x09\x0a\x0c\x0d\x20]+(\d+)[\x00\x09\x0a\x0c\x0d\x20]+obj\b")
    _ENDOBJ = re.compile(rb"(?<![/A-Za-z])endobj\b")
    _STREAM = re.compile(rb"(?<![/A-Za-z])stream(?:\r\n|\n|\r)")
    _ENDSTREAM = re.compile(rb"(?<![/A-Za-z])endstream\b")
    _XREF = re.compile(rb"(?m)^[\x00\x09\x0c\x20]*xref[\x00\x09\x0c\x20]*(?:\r?$)")
    _TRAILER = re.compile(rb"(?<![/A-Za-z])trailer\b")
    _STARTXREF = re.compile(rb"(?<![/A-Za-z])startxref\b")
    _EOF = re.compile(rb"%%EOF")
    _INTEGER_AFTER = re.compile(rb"[\x00\x09\x0a\x0c\x0d\x20]+(\d+)")
    _PREV = re.compile(rb"/Prev[\x00\x09\x0a\x0c\x0d\x20]+(\d+)\b")

    def analyze(self, reader: BinaryReader) -> PdfRawAnalysisResult:
        result = PdfRawAnalysisResult()
        if reader.is_empty:
            self._add(result, "pdf_header_absent", "Header PDF ausente", "A assinatura %PDF- não foi localizada.")
            self._add(result, "pdf_eof_absent", "Marcador %%EOF ausente", "Nenhum marcador %%EOF foi localizado.")
            return result

        with reader.path.open("rb") as stream:
            with mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
                self._parse(data, result)
        return result

    def _parse(self, data: mmap.mmap, result: PdfRawAnalysisResult) -> None:
        size = len(data)
        signature = BINARY_SIGNATURES["pdf"] + b"-"
        header = data.find(signature, 0, min(size, self.HEADER_LIMIT))
        if header < 0:
            self._add(result, "pdf_header_absent", "Header PDF ausente", "A assinatura %PDF- não foi localizada nos primeiros 1024 bytes.")
        else:
            result.header_offset = header
            version = re.match(rb"(\d+\.\d+)", data[header + len(signature):header + len(signature) + 16])
            result.version = version.group(1).decode("ascii") if version else None
            if header:
                self._add(result, "pdf_header_displaced", "Header PDF deslocado", f"A assinatura %PDF- foi localizada no offset {header}.", header)

        provisional_ranges = self._provisional_stream_ranges(data)
        object_matches = [
            match for match in self._OBJECT.finditer(data)
            if not self._inside(match.start(), provisional_ranges)
        ]
        stream_ranges: list[tuple[int, int]] = []
        for index, match in enumerate(object_matches):
            boundary = object_matches[index + 1].start() if index + 1 < len(object_matches) else size
            endobj = self._ENDOBJ.search(data, match.end(), boundary)
            object_end = endobj.end() if endobj else None
            body_end = endobj.start() if endobj else boundary
            stream_match = self._STREAM.search(data, match.end(), body_end)
            has_stream = stream_match is not None
            if stream_match:
                endstream = self._ENDSTREAM.search(data, stream_match.end(), body_end)
                if endstream:
                    stream_ranges.append((stream_match.end(), endstream.start()))
                else:
                    stream_ranges.append((stream_match.end(), body_end))
                    self._add(result, "pdf_stream_without_endstream", "Stream sem endstream", f"O objeto {match.group(1).decode()} {match.group(2).decode()} contém stream sem marcador endstream.", stream_match.start())
            if not endobj:
                self._add(result, "pdf_object_without_endobj", "Objeto sem endobj", f"O objeto {match.group(1).decode()} {match.group(2).decode()} não possui marcador endobj antes da próxima estrutura de objeto ou do fim do arquivo.", match.start())
            result.objects.append(PdfRawObject(int(match.group(1)), int(match.group(2)), match.start(), object_end, has_stream))

        outside = lambda offset: not self._inside(offset, stream_ranges)
        result.stream_count = sum(item.has_stream for item in result.objects)
        result.xref_offsets = [m.start() for m in self._XREF.finditer(data) if outside(m.start())]
        result.trailer_offsets = [m.start() for m in self._TRAILER.finditer(data) if outside(m.start())]
        result.eof_offsets = [m.start() for m in self._EOF.finditer(data) if outside(m.start())]
        result.prev_offsets = [int(m.group(1)) for m in self._PREV.finditer(data) if outside(m.start())]

        for match in self._STARTXREF.finditer(data):
            if not outside(match.start()):
                continue
            number = self._INTEGER_AFTER.match(data, match.end(), min(size, match.end() + 128))
            declared = int(number.group(1)) if number else None
            result.startxrefs.append(PdfStartXref(match.start(), declared))
            if declared is None:
                self._add(result, "pdf_startxref_invalid", "startxref sem número válido", "O marcador startxref não é seguido por um offset decimal válido.", match.start())
            elif declared >= size:
                self._add(result, "pdf_startxref_out_of_bounds", "Offset startxref fora do arquivo", f"O offset declarado {declared} está fora do tamanho do arquivo ({size} bytes).", match.start())

        for index, (obj, match) in enumerate(zip(result.objects, object_matches)):
            end = obj.end_offset
            if end is None:
                end = object_matches[index + 1].start() if index + 1 < len(object_matches) else size
            stream = self._STREAM.search(data, match.end(), end)
            dictionary_end = stream.start() if stream else end
            if self._has_name_pair(data, match.end(), dictionary_end, b"Type", b"XRef"):
                result.xref_stream_offsets.append(obj.start_offset)

        self._set_flags(data, stream_ranges, result)
        self._add_summary_findings(size, result)

    def _provisional_stream_ranges(
        self, data: mmap.mmap
    ) -> list[tuple[int, int]]:
        ranges: list[tuple[int, int]] = []
        position = 0
        size = len(data)
        while position < size:
            start = self._STREAM.search(data, position)
            if start is None:
                break
            end = self._ENDSTREAM.search(data, start.end())
            ranges.append((start.end(), end.start() if end else size))
            position = end.end() if end else size
        return ranges

    def _set_flags(self, data: mmap.mmap, ranges: list[tuple[int, int]], result: PdfRawAnalysisResult) -> None:
        flags = {
            "encrypted": (b"Encrypt",), "has_javascript": (b"JavaScript", b"JS"),
            "has_embedded_files": (b"EmbeddedFile", b"Filespec"), "has_open_action": (b"OpenAction",),
            "has_additional_actions": (b"AA",), "has_acroform": (b"AcroForm",), "has_xfa": (b"XFA",),
        }
        for attribute, names in flags.items():
            setattr(
                result,
                attribute,
                any(
                    any(self._name_offsets(data, name, ranges))
                    for name in names
                ),
            )

    def _add_summary_findings(self, size: int, result: PdfRawAnalysisResult) -> None:
        if not result.eof_offsets:
            self._add(result, "pdf_eof_absent", "Marcador %%EOF ausente", "Nenhum marcador %%EOF foi localizado.")
        else:
            last_end = result.eof_offsets[-1] + len(b"%%EOF")
            result.bytes_after_last_eof = size - last_end
            if result.bytes_after_last_eof:
                self._add(result, "pdf_bytes_after_eof", "Bytes após o último %%EOF", f"Foram localizados {result.bytes_after_last_eof} bytes após o último marcador %%EOF.", last_end)
        if len(result.eof_offsets) > 1:
            self._add(result, "pdf_multiple_eof", "Múltiplos marcadores %%EOF", f"Foram localizados {len(result.eof_offsets)} marcadores %%EOF, compatíveis com revisões incrementais ou processamentos posteriores.")
        if len(result.trailer_offsets) > 1:
            self._add(result, "pdf_multiple_trailers", "Múltiplos trailers", f"Foram localizados {len(result.trailer_offsets)} marcadores trailer.")
        summaries = [
            (result.prev_offsets, "pdf_prev_detected", "Cadeia /Prev detectada", "Foram localizadas referências /Prev na estrutura do PDF."),
            (result.encrypted, "pdf_encryption_detected", "Criptografia detectada", "A entrada /Encrypt foi localizada fora de streams."),
            (result.has_javascript, "pdf_javascript_detected", "JavaScript detectado", "Entradas /JavaScript ou /JS foram localizadas fora de streams."),
            (result.has_embedded_files, "pdf_embedded_files_detected", "Arquivos incorporados detectados", "Entradas /EmbeddedFile ou /Filespec foram localizadas fora de streams."),
            (result.has_open_action or result.has_additional_actions, "pdf_automatic_actions_detected", "Ações automáticas detectadas", "Entradas /OpenAction ou /AA foram localizadas fora de streams."),
            (result.has_acroform, "pdf_acroform_detected", "AcroForm detectado", "A entrada /AcroForm foi localizada fora de streams."),
            (result.has_xfa, "pdf_xfa_detected", "XFA detectado", "A entrada /XFA foi localizada fora de streams."),
        ]
        for present, code, title, description in summaries:
            if present:
                self._add(result, code, title, description)

    @staticmethod
    def _inside(offset: int, ranges: list[tuple[int, int]]) -> bool:
        return any(start <= offset < end for start, end in ranges)

    def _name_offsets(self, data: mmap.mmap, name: bytes, ranges: list[tuple[int, int]]) -> Iterator[int]:
        pattern = re.compile(rb"/" + re.escape(name) + rb"(?![#A-Za-z0-9])")
        return (match.start() for match in pattern.finditer(data) if not self._inside(match.start(), ranges))

    @staticmethod
    def _has_name_pair(data: mmap.mmap, start: int, end: int, first: bytes, second: bytes) -> bool:
        pattern = re.compile(rb"/" + first + rb"[\x00\x09\x0a\x0c\x0d\x20]+/" + second + rb"(?![#A-Za-z0-9])")
        return pattern.search(data, start, end) is not None

    @staticmethod
    def _add(result: PdfRawAnalysisResult, code: str, title: str, description: str, offset: int | None = None) -> None:
        result.findings.append(BinaryFinding(code=code, title=title, description=description, offset=offset))

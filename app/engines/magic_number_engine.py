from __future__ import annotations

from pathlib import Path
from zipfile import ZipFile, BadZipFile

from app.models import MagicNumberFinding, MagicNumberResult
from app.binary.signatures import BINARY_SIGNATURES


class MagicNumberEngine:
    """Engine de identificação e interpretação binária de arquivos."""

    HEADER_READ_SIZE = 512
    STRUCTURE_READ_LIMIT = 10 * 1024 * 1024

    SIGNATURES: list[dict] = [
        {
            "name": "PDF Document",
            "format": "PDF",
            "mime": "application/pdf",
            "extensions": {".pdf"},
            "magic": BINARY_SIGNATURES["pdf"] + b"-",
            "offset": 0,
            "confidence": 100,
            "description": "PDF Header",
        },
        {
            "name": "PNG Image",
            "format": "PNG",
            "mime": "image/png",
            "extensions": {".png"},
            "magic": BINARY_SIGNATURES["png"],
            "offset": 0,
            "confidence": 100,
            "description": "PNG Header",
        },
        {
            "name": "JPEG Image",
            "format": "JPEG",
            "mime": "image/jpeg",
            "extensions": {".jpg", ".jpeg"},
            "magic": BINARY_SIGNATURES["jpeg"],
            "offset": 0,
            "confidence": 95,
            "description": "JPEG Header",
        },
        {
            "name": "GIF Image",
            "format": "GIF",
            "mime": "image/gif",
            "extensions": {".gif"},
            "magic": b"GIF87a",
            "offset": 0,
            "confidence": 95,
            "description": "GIF87a Header",
        },
        {
            "name": "GIF Image",
            "format": "GIF",
            "mime": "image/gif",
            "extensions": {".gif"},
            "magic": b"GIF89a",
            "offset": 0,
            "confidence": 95,
            "description": "GIF89a Header",
        },
        {
            "name": "BMP Image",
            "format": "BMP",
            "mime": "image/bmp",
            "extensions": {".bmp"},
            "magic": b"BM",
            "offset": 0,
            "confidence": 90,
            "description": "BMP Header",
        },
        {
            "name": "ZIP Container",
            "format": "ZIP",
            "mime": "application/zip",
            "extensions": {".zip", ".docx", ".xlsx", ".pptx", ".apk", ".jar", ".odt", ".ods", ".odp"},
            "magic": BINARY_SIGNATURES["zip"],
            "offset": 0,
            "confidence": 90,
            "description": "ZIP Local File Header",
        },
        {
            "name": "RAR Archive",
            "format": "RAR",
            "mime": "application/vnd.rar",
            "extensions": {".rar"},
            "magic": BINARY_SIGNATURES["rar"] + b"\x1A\x07\x00",
            "offset": 0,
            "confidence": 95,
            "description": "RAR Header",
        },
        {
            "name": "7-Zip Archive",
            "format": "7Z",
            "mime": "application/x-7z-compressed",
            "extensions": {".7z"},
            "magic": BINARY_SIGNATURES["7z"],
            "offset": 0,
            "confidence": 95,
            "description": "7Z Header",
        },
        {
            "name": "Windows Executable",
            "format": "EXE/DLL",
            "mime": "application/vnd.microsoft.portable-executable",
            "extensions": {".exe", ".dll", ".sys"},
            "magic": b"MZ",
            "offset": 0,
            "confidence": 90,
            "description": "MZ Executable Header",
        },
        {
            "name": "SQLite Database",
            "format": "SQLITE",
            "mime": "application/vnd.sqlite3",
            "extensions": {".sqlite", ".sqlite3", ".db"},
            "magic": BINARY_SIGNATURES["sqlite"],
            "offset": 0,
            "confidence": 100,
            "description": "SQLite Header",
        },
        {
            "name": "WebP Image",
            "format": "WEBP",
            "mime": "image/webp",
            "extensions": {".webp"},
            "magic": b"RIFF",
            "offset": 0,
            "confidence": 80,
            "description": "RIFF Container",
        },
    ]

    def analyze(self, file_path: Path) -> MagicNumberResult:
        header = self._read_header(file_path)
        sample = self._read_sample(file_path)

        extension = file_path.suffix.lower()
        file_size = file_path.stat().st_size

        detected = self._detect_primary_signature(header)

        if detected is None:
            result = self._unknown_result(file_path, header)
        else:
            result = self._build_result(file_path, header, sample, detected)

        if result.detected_format == "ZIP":
            self._enrich_zip_container(file_path, result)

        if result.detected_format == "PDF":
            self._analyze_pdf_structure(sample, file_size, result)

        self._finalize_interpretation(result)

        return result

    def _detect_primary_signature(self, header: bytes) -> dict | None:
        for signature in self.SIGNATURES:
            magic = signature["magic"]
            offset = signature.get("offset", 0)

            if header[offset:offset + len(magic)] == magic:
                return signature

        return None

    def _build_result(
        self,
        file_path: Path,
        header: bytes,
        sample: bytes,
        detected: dict,
    ) -> MagicNumberResult:
        extension = file_path.suffix.lower()
        magic = detected["magic"]

        extension_matches = extension in detected["extensions"]

        finding = MagicNumberFinding(
            offset=detected["offset"],
            hex_value=self._to_hex(magic),
            ascii_value=self._to_ascii(magic),
            description=detected["description"],
            confidence=detected["confidence"],
        )

        confidence = detected["confidence"]

        if not extension_matches:
            confidence = max(0, confidence - 25)

        return MagicNumberResult(
            detected_type=detected["name"],
            detected_format=detected["format"],
            signature=self._to_hex(magic),
            ascii_signature=self._to_ascii(magic),
            extension=extension,
            extension_matches=extension_matches,
            confidence=confidence,
            mime_type=detected["mime"],
            offset=detected["offset"],
            header_preview_hex=self._hex_dump(header[:128]),
            header_preview_ascii=self._ascii_dump(header[:128]),
            is_corrupted=False,
            findings=[finding],
            forensic_interpretation=[],
            conclusion="",
        )

    def _unknown_result(self, file_path: Path, header: bytes) -> MagicNumberResult:
        return MagicNumberResult(
            detected_type="Desconhecido",
            detected_format="UNKNOWN",
            signature=self._to_hex(header[:16]),
            ascii_signature=self._to_ascii(header[:16]),
            extension=file_path.suffix.lower(),
            extension_matches=False,
            confidence=0,
            mime_type="application/octet-stream",
            offset=0,
            header_preview_hex=self._hex_dump(header[:128]),
            header_preview_ascii=self._ascii_dump(header[:128]),
            is_corrupted=False,
            findings=[],
            forensic_interpretation=[
                "Não foi possível identificar assinatura binária conhecida no cabeçalho do arquivo.",
            ],
            conclusion="Formato não identificado pela base atual de assinaturas.",
        )

    def _analyze_pdf_structure(
        self,
        sample: bytes,
        file_size: int,
        result: MagicNumberResult,
    ) -> None:
        checks = [
            (b"%PDF-", "PDF Header", 100),
            (b"xref", "Cross Reference Table", 90),
            (b"trailer", "Trailer Dictionary", 90),
            (b"%%EOF", "End Of File Marker", 100),
        ]

        for marker, description, confidence in checks:
            offset = sample.find(marker)

            if offset >= 0:
                if not any(f.offset == offset and f.hex_value == self._to_hex(marker) for f in result.findings):
                    result.findings.append(
                        MagicNumberFinding(
                            offset=offset,
                            hex_value=self._to_hex(marker),
                            ascii_value=self._to_ascii(marker),
                            description=description,
                            confidence=confidence,
                            status="Válido",
                        )
                    )

        has_eof_near_end = b"%%EOF" in sample[-2048:]

        if not has_eof_near_end:
            result.is_corrupted = True
            result.confidence = max(0, result.confidence - 30)
            result.forensic_interpretation.append(
                "O marcador %%EOF não foi localizado próximo ao final do arquivo, podendo indicar truncamento ou reprocessamento incompleto."
            )

        if b"xref" not in sample and b"/XRef" not in sample:
            result.confidence = max(0, result.confidence - 10)
            result.forensic_interpretation.append(
                "A estrutura de referência cruzada tradicional não foi localizada na amostra analisada."
            )

    def _enrich_zip_container(
        self,
        file_path: Path,
        result: MagicNumberResult,
    ) -> None:
        try:
            with ZipFile(file_path, "r") as zip_file:
                names = set(zip_file.namelist())

            if "[Content_Types].xml" in names:
                if "word/document.xml" in names:
                    result.detected_type = "Microsoft Word Document"
                    result.detected_format = "DOCX"
                    result.mime_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                elif "xl/workbook.xml" in names:
                    result.detected_type = "Microsoft Excel Spreadsheet"
                    result.detected_format = "XLSX"
                    result.mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                elif "ppt/presentation.xml" in names:
                    result.detected_type = "Microsoft PowerPoint Presentation"
                    result.detected_format = "PPTX"
                    result.mime_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"

            elif "AndroidManifest.xml" in names:
                result.detected_type = "Android Application Package"
                result.detected_format = "APK"
                result.mime_type = "application/vnd.android.package-archive"

            elif "META-INF/MANIFEST.MF" in names:
                result.detected_type = "Java Archive"
                result.detected_format = "JAR"
                result.mime_type = "application/java-archive"

            result.findings.append(
                MagicNumberFinding(
                    offset=0,
                    hex_value="50 4B 03 04",
                    ascii_value="PK..",
                    description="ZIP container estruturalmente legível",
                    confidence=95,
                    status="Válido",
                )
            )

        except BadZipFile:
            result.is_corrupted = True
            result.confidence = max(0, result.confidence - 35)
            result.forensic_interpretation.append(
                "O arquivo possui assinatura ZIP, mas a estrutura interna não pôde ser aberta como ZIP válido."
            )

    def _finalize_interpretation(self, result: MagicNumberResult) -> None:
        if result.extension_matches:
            result.forensic_interpretation.append(
                f"A extensão {result.extension} é compatível com o formato detectado."
            )
        else:
            result.forensic_interpretation.append(
                f"A extensão {result.extension or '(sem extensão)'} não é compatível ou não pôde ser confirmada para o formato detectado."
            )

        if result.confidence >= 90 and not result.is_corrupted:
            result.conclusion = (
                f"Arquivo {result.detected_format} íntegro e compatível com a assinatura binária identificada."
            )
        elif result.confidence >= 60:
            result.conclusion = (
                f"Arquivo identificado como {result.detected_format}, porém com ressalvas técnicas na estrutura ou extensão."
            )
        elif result.detected_format == "UNKNOWN":
            result.conclusion = "Não foi possível identificar o formato do arquivo pela assinatura binária."
        else:
            result.conclusion = (
                "Foram identificadas inconsistências relevantes na assinatura ou estrutura do arquivo."
            )

    def search_bytes(
        self,
        file_path: Path,
        query: str,
        mode: str = "text",
        max_results: int = 100,
    ) -> list[MagicNumberFinding]:
        data = self._read_sample(file_path, limit=self.STRUCTURE_READ_LIMIT)

        if mode == "hex":
            needle = bytes.fromhex(query.replace(" ", ""))
        else:
            needle = query.encode("utf-8", errors="ignore")

        results = []
        start = 0

        while len(results) < max_results:
            offset = data.find(needle, start)

            if offset == -1:
                break

            results.append(
                MagicNumberFinding(
                    offset=offset,
                    hex_value=self._to_hex(needle),
                    ascii_value=self._to_ascii(needle),
                    description=f"Ocorrência encontrada para busca: {query}",
                    confidence=100,
                    status="Encontrado",
                )
            )

            start = offset + 1

        return results

    def _read_header(self, file_path: Path) -> bytes:
        with file_path.open("rb") as file:
            return file.read(self.HEADER_READ_SIZE)

    def _read_sample(
        self,
        file_path: Path,
        limit: int | None = None,
    ) -> bytes:
        read_limit = limit or self.STRUCTURE_READ_LIMIT

        with file_path.open("rb") as file:
            return file.read(read_limit)

    def _to_hex(self, data: bytes) -> str:
        return data.hex(" ").upper()

    def _to_ascii(self, data: bytes) -> str:
        return "".join(
            chr(byte) if 32 <= byte <= 126 else "."
            for byte in data
        )

    def _hex_dump(self, data: bytes, width: int = 16) -> str:
        lines = []

        for offset in range(0, len(data), width):
            chunk = data[offset:offset + width]
            hex_part = " ".join(f"{byte:02X}" for byte in chunk)
            ascii_part = self._to_ascii(chunk)

            lines.append(
                f"{offset:08X}  {hex_part:<48}  {ascii_part}"
            )

        return "\n".join(lines)

    def _ascii_dump(self, data: bytes) -> str:
        return self._to_ascii(data)

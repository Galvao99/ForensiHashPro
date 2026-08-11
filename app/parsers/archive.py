from __future__ import annotations

import os
import re
import stat
import tempfile
import time
import zipfile
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path, PurePosixPath
from typing import BinaryIO
from uuid import NAMESPACE_URL, uuid5

from app.parsers.identification import identify_bytes
from app.parsers.models import (
    ArchiveEntry,
    ArchiveInspectionResult,
    ArchiveWarning,
    ArtifactIdentification,
    ParsedArtifact,
)


_EXECUTABLE = {".exe", ".dll", ".scr", ".com", ".msi", ".sys"}
_SCRIPT = {".js", ".vbs", ".ps1", ".bat", ".cmd", ".hta"}
_OTHER_ACTIVE = {".jar", ".lnk"}
_MACRO_OFFICE = {".docm", ".xlsm", ".pptm"}
_DECOY_EXTENSIONS = {
    ".pdf", ".jpg", ".jpeg", ".png", ".gif", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".txt", ".json",
}
_EXTENSION_TYPES = {
    ".pdf": "PDF", ".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG",
    ".json": "JSON", ".zip": "ZIP", ".exe": "PE", ".dll": "PE",
    ".scr": "PE", ".com": "PE",
}
_WINDOWS_ABSOLUTE = re.compile(r"^[a-zA-Z]:[/\\]")


@dataclass(frozen=True, slots=True)
class ArchiveLimits:
    max_entries: int = 1_000
    max_total_uncompressed_bytes: int = 1024 * 1024 * 1024
    max_entry_uncompressed_bytes: int = 256 * 1024 * 1024
    max_compression_ratio: float = 200.0
    max_nesting_depth: int = 3
    timeout_seconds: int = 30
    chunk_size: int = 64 * 1024
    magic_read_bytes: int = 8 * 1024

    def validate(self) -> None:
        integers = {
            "max_entries": (self.max_entries, 1, 100_000),
            "max_total_uncompressed_bytes": (self.max_total_uncompressed_bytes, 1, 100 * 1024**3),
            "max_entry_uncompressed_bytes": (self.max_entry_uncompressed_bytes, 1, 10 * 1024**3),
            "max_nesting_depth": (self.max_nesting_depth, 0, 20),
            "timeout_seconds": (self.timeout_seconds, 1, 3600),
            "chunk_size": (self.chunk_size, 1024, 4 * 1024 * 1024),
            "magic_read_bytes": (self.magic_read_bytes, 16, 1024 * 1024),
        }
        for name, (value, minimum, maximum) in integers.items():
            if not minimum <= value <= maximum:
                raise ValueError(f"{name} deve estar entre {minimum} e {maximum}.")
        if not 1 <= self.max_compression_ratio <= 1_000_000:
            raise ValueError("max_compression_ratio deve estar entre 1 e 1000000.")
        if self.max_entry_uncompressed_bytes > self.max_total_uncompressed_bytes:
            raise ValueError("O limite por entrada não pode exceder o limite total.")

    @classmethod
    def from_env(cls) -> "ArchiveLimits":
        defaults = cls()
        def integer(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, str(default)).strip())
            except ValueError as error:
                raise ValueError(f"{name} deve ser inteiro.") from error

        try:
            ratio = float(os.environ.get(
                "FORENSIHASH_ARCHIVE_MAX_COMPRESSION_RATIO", str(defaults.max_compression_ratio)
            ).strip())
        except ValueError as error:
            raise ValueError("FORENSIHASH_ARCHIVE_MAX_COMPRESSION_RATIO deve ser numérico.") from error
        limits = cls(
            max_entries=integer("FORENSIHASH_ARCHIVE_MAX_ENTRIES", defaults.max_entries),
            max_total_uncompressed_bytes=integer(
                "FORENSIHASH_ARCHIVE_MAX_TOTAL_UNCOMPRESSED_BYTES",
                defaults.max_total_uncompressed_bytes,
            ),
            max_entry_uncompressed_bytes=integer(
                "FORENSIHASH_ARCHIVE_MAX_ENTRY_UNCOMPRESSED_BYTES",
                defaults.max_entry_uncompressed_bytes,
            ),
            max_compression_ratio=ratio,
            max_nesting_depth=integer(
                "FORENSIHASH_ARCHIVE_MAX_NESTING_DEPTH", defaults.max_nesting_depth
            ),
            timeout_seconds=integer(
                "FORENSIHASH_ARCHIVE_INSPECTION_TIMEOUT_SECONDS", defaults.timeout_seconds
            ),
        )
        limits.validate()
        return limits


@dataclass(slots=True)
class _Budget:
    deadline: float
    entries: int = 0
    actual_bytes: int = 0
    declared_bytes: int = 0


class ArchiveInspectionTimeout(TimeoutError):
    pass


class ArchiveInspectionEngine:
    """Inspeção ZIP estática, limitada e sem materializar paths das entradas."""

    def __init__(self, limits: ArchiveLimits | None = None) -> None:
        self.limits = limits or ArchiveLimits.from_env()
        self.limits.validate()

    def inspect(self, path: Path) -> ArchiveInspectionResult:
        result = ArchiveInspectionResult()
        budget = _Budget(time.monotonic() + self.limits.timeout_seconds)
        try:
            with zipfile.ZipFile(Path(path), "r") as archive:
                result.entries = self._inspect_zip(archive, result, budget, depth=0, parent="")
        except ArchiveInspectionTimeout:
            result.state = "partial"
            self._warn(result, "archive_timeout", "A inspeção excedeu o tempo configurado.")
            result.limitations.append("A inspeção profunda foi interrompida pelo timeout configurado.")
        except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, RuntimeError) as error:
            result.state = "partial"
            self._warn(
                result, "corrupted_entry",
                "A estrutura ZIP não pôde ser inspecionada integralmente.",
                details={"error_type": type(error).__name__},
            )
            result.limitations.append("O arquivo compactado está corrompido ou usa estrutura não suportada.")
        result.total_entries = budget.entries
        result.declared_uncompressed_size = budget.declared_bytes
        result.inspected_uncompressed_bytes = budget.actual_bytes
        if result.warnings and result.state == "completed":
            result.state = "partial"
        return result

    def _inspect_zip(
        self, archive: zipfile.ZipFile, result: ArchiveInspectionResult,
        budget: _Budget, *, depth: int, parent: str,
    ) -> list[ArchiveEntry]:
        self._deadline(budget)
        result.max_depth = max(result.max_depth, depth)
        entries: list[ArchiveEntry] = []
        for info in archive.infolist():
            self._deadline(budget)
            if budget.entries >= self.limits.max_entries:
                self._warn(result, "archive_entry_limit", "A quantidade de entradas excede o limite configurado.")
                result.limitations.append("Entradas adicionais não foram inspecionadas.")
                break
            budget.entries += 1
            budget.declared_bytes += max(0, info.file_size)
            result.total_compressed_size += max(0, info.compress_size)
            internal_path = info.filename
            name = PurePosixPath(internal_path.replace("\\", "/")).name or internal_path
            extension = Path(name).suffix.lower()
            ratio = self._ratio(info.file_size, info.compress_size)
            encrypted = bool(info.flag_bits & 0x1)
            entry_type = self._entry_type(info)
            ref = str(uuid5(NAMESPACE_URL, f"forensihash:embedded:{parent}:{internal_path}:{depth}"))
            entry = ArchiveEntry(
                embedded_artifact_ref=ref, filename=name, internal_path=internal_path,
                extension=extension, compressed_size=info.compress_size,
                uncompressed_size=info.file_size, compression_ratio=ratio,
                crc32=f"{info.CRC:08X}", compression_method=info.compress_type,
                encrypted=encrypted, entry_type=entry_type, nested_depth=depth,
            )
            entries.append(entry)
            if entry_type == "directory":
                result.directory_entries += 1
                continue
            self._classify_name(entry, result)
            if self._path_traversal(internal_path):
                self._flag(entry, result, "archive_path_traversal", "A entrada contém path que sairia de uma raiz de extração.")
            if encrypted:
                result.encrypted_entries += 1
                self._flag(entry, result, "encrypted_entry", "A entrada está criptografada e não foi aberta.")
                entry.limitations.append("O conteúdo não pôde ser inspecionado sem credencial de descriptografia.")
                continue
            if entry_type != "file":
                entry.limitations.append("Entrada especial não foi materializada nem aberta.")
                continue
            if info.file_size > self.limits.max_entry_uncompressed_bytes:
                self._flag(entry, result, "archive_expansion_limit", "A entrada excede o limite descomprimido por arquivo.")
                entry.limitations.append("Conteúdo e hash não foram inspecionados por limite de tamanho.")
                continue
            if budget.declared_bytes > self.limits.max_total_uncompressed_bytes:
                self._flag(entry, result, "archive_expansion_limit", "O total descomprimido declarado excede o limite configurado.")
                result.limitations.append("A inspeção de conteúdo foi interrompida pelo limite total declarado.")
                break
            if ratio is not None and ratio > self.limits.max_compression_ratio:
                self._flag(entry, result, "archive_expansion_limit", "A taxa de expansão do conteúdo excede o limite configurado.")
                entry.limitations.append("Conteúdo não descomprimido devido à taxa de expansão.")
                continue
            try:
                self._stream_entry(archive, info, entry, result, budget, depth)
            except (zipfile.BadZipFile, RuntimeError, OSError, EOFError) as error:
                self._flag(
                    entry, result, "corrupted_entry", "A entrada não pôde ser lida integralmente.",
                    {"error_type": type(error).__name__},
                )
                entry.limitations.append("Conteúdo ou hash interno ficou indisponível.")
        return entries

    def _stream_entry(
        self, archive: zipfile.ZipFile, info: zipfile.ZipInfo, entry: ArchiveEntry,
        result: ArchiveInspectionResult, budget: _Budget, depth: int,
    ) -> None:
        digest = sha256()
        header = bytearray()
        spool: BinaryIO | None = None
        try:
            with archive.open(info, "r") as stream:
                while True:
                    self._deadline(budget)
                    chunk = stream.read(self.limits.chunk_size)
                    if not chunk:
                        break
                    budget.actual_bytes += len(chunk)
                    if budget.actual_bytes > self.limits.max_total_uncompressed_bytes:
                        raise _StreamingLimit
                    digest.update(chunk)
                    if len(header) < self.limits.magic_read_bytes:
                        header.extend(chunk[: self.limits.magic_read_bytes - len(header)])
                    if spool is not None:
                        spool.write(chunk)
                    elif header.startswith((b"PK\x03\x04", b"PK\x05\x06")):
                        spool = tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024)
                        spool.write(chunk)
            entry.sha256 = digest.hexdigest()
            detected = identify_bytes(bytes(header))
            if detected:
                entry.detected_type, entry.mime_type, entry.magic_signature = detected
                self._extension_mismatch(entry, result)
            if entry.detected_type == "PE" and "executable_content_detected" not in entry.inspection_flags:
                result.executable_entries += 1
                self._flag(entry, result, "executable_content_detected", "Conteúdo executável detectado no arquivo compactado.")
            if entry.detected_type == "ZIP":
                self._flag(entry, result, "nested_archive_detected", "Arquivo compactado aninhado identificado.")
                if depth >= self.limits.max_nesting_depth:
                    self._flag(entry, result, "archive_depth_limit", "A profundidade máxima de arquivos aninhados foi atingida.")
                    entry.limitations.append("O archive aninhado não foi inspecionado além deste nível.")
                elif spool is not None:
                    spool.seek(0)
                    with zipfile.ZipFile(spool, "r") as nested:
                        entry.children = self._inspect_zip(
                            nested, result, budget, depth=depth + 1,
                            parent=entry.embedded_artifact_ref,
                        )
        except _StreamingLimit:
            self._flag(entry, result, "archive_expansion_limit", "O limite total foi atingido durante leitura streaming.")
            entry.limitations.append("Leitura e hash interrompidos pelo limite real de bytes.")
            entry.sha256 = None
        finally:
            if spool is not None:
                spool.close()

    def _classify_name(self, entry: ArchiveEntry, result: ArchiveInspectionResult) -> None:
        suffixes = [item.lower() for item in Path(entry.filename).suffixes]
        extension = entry.extension
        if extension in _EXECUTABLE or extension in _OTHER_ACTIVE:
            result.executable_entries += 1
            self._flag(entry, result, "executable_content_detected", "Conteúdo executável ou carregável detectado no arquivo compactado.")
        if extension in _SCRIPT:
            result.script_entries += 1
            self._flag(entry, result, "script_content_detected", "Conteúdo de script detectado no arquivo compactado.")
        if extension in _MACRO_OFFICE:
            result.macro_enabled_entries += 1
            self._flag(entry, result, "macro_enabled_office_detected", "Documento Office habilitado para macros detectado.")
        if len(suffixes) >= 2 and suffixes[-1] in (_EXECUTABLE | _SCRIPT | _OTHER_ACTIVE) and suffixes[-2] in _DECOY_EXTENSIONS:
            self._flag(entry, result, "double_extension", "Nome de entrada com dupla extensão identificada.")

    def _extension_mismatch(self, entry: ArchiveEntry, result: ArchiveInspectionResult) -> None:
        expected = _EXTENSION_TYPES.get(entry.extension)
        if expected and entry.detected_type and expected != entry.detected_type:
            self._flag(
                entry, result, "extension_content_mismatch",
                f"A extensão declarada indica {expected}, porém a assinatura binária indica {entry.detected_type}.",
                {"declared_type": expected, "detected_type": entry.detected_type},
            )

    @staticmethod
    def _entry_type(info: zipfile.ZipInfo) -> str:
        if info.is_dir():
            return "directory"
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if file_type == stat.S_IFLNK:
            return "symlink"
        if file_type not in {0, stat.S_IFREG}:
            return "special"
        return "file"

    @staticmethod
    def _path_traversal(value: str) -> bool:
        normalized = value.replace("\\", "/")
        return (
            normalized.startswith("/")
            or bool(_WINDOWS_ABSOLUTE.match(value))
            or ".." in PurePosixPath(normalized).parts
        )

    @staticmethod
    def _ratio(uncompressed: int, compressed: int) -> float | None:
        if compressed == 0:
            return None if uncompressed == 0 else float("inf")
        return uncompressed / compressed

    @staticmethod
    def _deadline(budget: _Budget) -> None:
        if time.monotonic() > budget.deadline:
            raise ArchiveInspectionTimeout

    @staticmethod
    def _warn(
        result: ArchiveInspectionResult, code: str, message: str,
        entry_ref: str | None = None, details: dict | None = None,
    ) -> None:
        result.warnings.append(ArchiveWarning(code, message, entry_ref, details or {}))

    def _flag(
        self, entry: ArchiveEntry, result: ArchiveInspectionResult,
        code: str, message: str, details: dict | None = None,
    ) -> None:
        if code not in entry.inspection_flags:
            entry.inspection_flags.append(code)
            self._warn(result, code, message, entry.embedded_artifact_ref, details)


class _StreamingLimit(RuntimeError):
    pass


class ZipArtifactParser:
    parser_id = "archive_zip_v1"
    supported_types = frozenset({"ZIP"})
    priority = 100

    def __init__(self, engine: ArchiveInspectionEngine | None = None) -> None:
        self.engine = engine or ArchiveInspectionEngine()

    def can_parse(self, identification: ArtifactIdentification) -> bool:
        return identification.detected_type == "ZIP" or identification.mime_type == "application/zip"

    def parse(self, path: Path, identification: ArtifactIdentification) -> ParsedArtifact:
        archive = self.engine.inspect(path)
        return ParsedArtifact(
            parser_id=self.parser_id, detected_type="ZIP",
            declared_extension=identification.declared_extension,
            mime_type=identification.mime_type, magic_signature=identification.magic_signature,
            state=archive.state,
            metadata={
                "archive_type": archive.archive_type,
                "total_entries": archive.total_entries,
                "directory_entries": archive.directory_entries,
                "total_compressed_size": archive.total_compressed_size,
                "declared_uncompressed_size": archive.declared_uncompressed_size,
                "inspected_uncompressed_bytes": archive.inspected_uncompressed_bytes,
                "max_depth": archive.max_depth,
                "encrypted_entries": archive.encrypted_entries,
                "executable_entries": archive.executable_entries,
                "script_entries": archive.script_entries,
                "macro_enabled_entries": archive.macro_enabled_entries,
            },
            structure={"archive_type": "ZIP"}, embedded_artifacts=archive.entries,
            warnings=archive.warnings, limitations=archive.limitations,
        )

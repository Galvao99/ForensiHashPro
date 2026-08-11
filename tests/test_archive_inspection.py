from __future__ import annotations

import io
import struct
import zipfile
from hashlib import sha256
from pathlib import Path

import pytest

from app.engines.magic_number_engine import MagicNumberEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.hash_engine import HashEngine
from app.engines.finding_engine import FindingsEngine
from app.engines.pdf_structure_engine import PDFStructureEngine
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.models import MetadataResult
from app.processing import ProcessingStatus, StepResult
from app.contracts import LegacyAnalysisAdapter, AnalysisState
from app.parsers import (
    ArchiveInspectionEngine,
    ArchiveLimits,
    ArtifactIdentification,
    BinaryFallbackParser,
    ParserRegistry,
    ZipArtifactParser,
)


def _zip(path: Path, entries: dict[str, bytes], compression=zipfile.ZIP_DEFLATED) -> Path:
    with zipfile.ZipFile(path, "w", compression=compression) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return path


def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return stream.getvalue()


def _engine(**overrides) -> ArchiveInspectionEngine:
    values = dict(
        max_entries=100, max_total_uncompressed_bytes=10 * 1024 * 1024,
        max_entry_uncompressed_bytes=5 * 1024 * 1024,
        max_compression_ratio=500, max_nesting_depth=2, timeout_seconds=10,
        chunk_size=1024, magic_read_bytes=128,
    )
    values.update(overrides)
    return ArchiveInspectionEngine(ArchiveLimits(**values))


def _flags(result) -> set[str]:
    return {warning.code for warning in result.warnings}


def test_empty_zip_is_identified_and_inspected(tmp_path):
    path = _zip(tmp_path / "empty.zip", {})
    magic = MagicNumberEngine().analyze(path)
    result = _engine().inspect(path)
    assert magic.detected_format == "ZIP"
    assert result.total_entries == 0 and result.state == "completed"


@pytest.mark.parametrize(
    ("name", "content", "detected"),
    [
        ("contrato.pdf", b"%PDF-1.7\n%%EOF", "PDF"),
        ("selfie.jpg", b"\xff\xd8\xff\xe0synthetic", "JPEG"),
        ("dados.json", b'{"ok": true}', "JSON"),
    ],
)
def test_common_entries_are_identified_by_internal_magic(tmp_path, name, content, detected):
    result = _engine().inspect(_zip(tmp_path / "evidence.zip", {name: content}))
    entry = result.entries[0]
    assert entry.detected_type == detected
    assert entry.sha256 == sha256(content).hexdigest()
    assert entry.crc32 and entry.compression_method == zipfile.ZIP_DEFLATED


@pytest.mark.parametrize(
    ("name", "expected_flag"),
    [
        ("setup.exe", "executable_content_detected"),
        ("library.dll", "executable_content_detected"),
        ("install.js", "script_content_detected"),
        ("run.ps1", "script_content_detected"),
        ("run.bat", "script_content_detected"),
        ("document.docm", "macro_enabled_office_detected"),
        ("sheet.xlsm", "macro_enabled_office_detected"),
        ("slides.pptm", "macro_enabled_office_detected"),
    ],
)
def test_active_content_names_produce_only_factual_flags(tmp_path, name, expected_flag):
    result = _engine().inspect(_zip(tmp_path / "active.zip", {name: b"synthetic"}))
    assert expected_flag in result.entries[0].inspection_flags
    serialized = str(result).lower()
    assert "malware" not in serialized and "trojan" not in serialized and "virus" not in serialized


@pytest.mark.parametrize("name", ["contrato.pdf.exe", "foto.jpg.scr", "documento.docx.js"])
def test_double_extension_is_reported_factually(tmp_path, name):
    result = _engine().inspect(_zip(tmp_path / "double.zip", {name: b"synthetic"}))
    assert "double_extension" in result.entries[0].inspection_flags


def test_pdf_name_with_pe_magic_reports_mismatch_and_executable_content(tmp_path):
    result = _engine().inspect(_zip(tmp_path / "spoof.zip", {"contrato.pdf": b"MZsynthetic"}))
    entry = result.entries[0]
    assert entry.detected_type == "PE"
    assert {"extension_content_mismatch", "executable_content_detected"} <= set(entry.inspection_flags)


def test_exe_name_with_non_executable_content_keeps_name_flag_without_invented_magic(tmp_path):
    result = _engine().inspect(_zip(tmp_path / "named.zip", {"note.exe": b"plain text"}))
    entry = result.entries[0]
    assert entry.detected_type is None
    assert "executable_content_detected" in entry.inspection_flags
    assert "extension_content_mismatch" not in entry.inspection_flags


@pytest.mark.parametrize(
    "name",
    ["../config", "../../arquivo.exe", "/absolute/path", "C:\\Windows\\system.ini"],
)
def test_path_traversal_variants_are_detected_without_materialization(tmp_path, name):
    path = _zip(tmp_path / "paths.zip", {name: b"data"})
    before = {item.name for item in tmp_path.iterdir()}
    result = _engine().inspect(path)
    after = {item.name for item in tmp_path.iterdir()}
    assert "archive_path_traversal" in result.entries[0].inspection_flags
    assert before == after == {"paths.zip"}


def test_entry_count_limit_stops_listing(tmp_path):
    path = _zip(tmp_path / "many.zip", {f"{index}.txt": b"x" for index in range(5)})
    result = _engine(max_entries=2).inspect(path)
    assert result.total_entries == 2
    assert "archive_entry_limit" in _flags(result)


def test_entry_declared_size_limit_prevents_content_read_and_hash(tmp_path):
    path = _zip(tmp_path / "large.zip", {"large.bin": b"x" * 4096})
    result = _engine(max_entry_uncompressed_bytes=100).inspect(path)
    assert result.entries[0].sha256 is None
    assert "archive_expansion_limit" in result.entries[0].inspection_flags


def test_total_declared_limit_stops_deep_inspection(tmp_path):
    path = _zip(tmp_path / "total.zip", {"a.bin": b"a" * 80, "b.bin": b"b" * 80})
    result = _engine(max_total_uncompressed_bytes=100, max_entry_uncompressed_bytes=100).inspect(path)
    assert "archive_expansion_limit" in _flags(result)
    assert result.entries[-1].sha256 is None


def test_compression_ratio_limit_is_applied_before_decompression(tmp_path):
    path = _zip(tmp_path / "ratio.zip", {"expanded.txt": b"A" * 100_000})
    result = _engine(max_compression_ratio=2).inspect(path)
    assert result.entries[0].sha256 is None
    assert "archive_expansion_limit" in result.entries[0].inspection_flags


def test_zero_compressed_size_is_handled_without_division_error(tmp_path):
    path = _zip(tmp_path / "zero.zip", {"empty.txt": b""}, zipfile.ZIP_STORED)
    entry = _engine().inspect(path).entries[0]
    assert entry.compressed_size == 0 and entry.compression_ratio is None
    assert entry.sha256 == sha256(b"").hexdigest()


def test_nested_zip_depth_one_builds_tree(tmp_path):
    nested = _zip_bytes({"inside.json": b"{}"})
    result = _engine().inspect(_zip(tmp_path / "nested.zip", {"anexos.zip": nested}))
    entry = result.entries[0]
    assert "nested_archive_detected" in entry.inspection_flags
    assert entry.children[0].filename == "inside.json"
    assert entry.children[0].nested_depth == 1


def test_nested_zip_at_limit_is_inspected_but_next_level_is_not(tmp_path):
    level_two = _zip_bytes({"leaf.txt": b"leaf"})
    level_one = _zip_bytes({"level-two.zip": level_two})
    result = _engine(max_nesting_depth=1).inspect(
        _zip(tmp_path / "nested.zip", {"level-one.zip": level_one})
    )
    second = result.entries[0].children[0]
    assert "archive_depth_limit" in second.inspection_flags
    assert second.children == []


def test_depth_zero_detects_nested_archive_without_opening_it(tmp_path):
    nested = _zip_bytes({"leaf.txt": b"leaf"})
    result = _engine(max_nesting_depth=0).inspect(
        _zip(tmp_path / "nested.zip", {"nested.zip": nested})
    )
    assert "archive_depth_limit" in result.entries[0].inspection_flags
    assert result.entries[0].children == []


def _mark_encrypted(path: Path) -> None:
    data = bytearray(path.read_bytes())
    local = data.find(b"PK\x03\x04")
    central = data.find(b"PK\x01\x02")
    struct.pack_into("<H", data, local + 6, struct.unpack_from("<H", data, local + 6)[0] | 1)
    struct.pack_into("<H", data, central + 8, struct.unpack_from("<H", data, central + 8)[0] | 1)
    path.write_bytes(data)


def test_encrypted_entry_is_not_opened(tmp_path):
    path = _zip(tmp_path / "encrypted.zip", {"secret.txt": b"secret"})
    _mark_encrypted(path)
    result = _engine().inspect(path)
    assert result.encrypted_entries == 1
    assert result.entries[0].sha256 is None
    assert "encrypted_entry" in result.entries[0].inspection_flags


def test_corrupted_zip_returns_safe_partial_result(tmp_path):
    path = tmp_path / "broken.zip"
    path.write_bytes(b"PK\x03\x04truncated")
    result = _engine().inspect(path)
    assert result.state == "partial"
    assert "corrupted_entry" in _flags(result)
    assert "Traceback" not in str(result)


def test_directory_and_symlink_entries_are_not_materialized(tmp_path):
    path = tmp_path / "special.zip"
    link = zipfile.ZipInfo("link-to-file")
    link.create_system = 3
    link.external_attr = (0o120777 << 16)
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("folder/", b"")
        archive.writestr(link, b"target.txt")
    result = _engine().inspect(path)
    by_path = {entry.internal_path: entry for entry in result.entries}
    assert by_path["folder/"].entry_type == "directory"
    assert by_path["link-to-file"].entry_type == "symlink"
    assert by_path["link-to-file"].sha256 is None
    assert not (tmp_path / "link-to-file").exists()


def test_large_entry_is_hashed_streaming_with_small_chunks(tmp_path):
    content = (b"streaming-content" * 20_000)
    path = _zip(tmp_path / "stream.zip", {"large.dat": content}, zipfile.ZIP_STORED)
    result = _engine(chunk_size=1024).inspect(path)
    assert result.inspected_uncompressed_bytes == len(content)
    assert result.entries[0].sha256 == sha256(content).hexdigest()


def test_actual_streaming_limit_interrupts_hash():
    from app.parsers.archive import _Budget
    from app.parsers.models import ArchiveEntry, ArchiveInspectionResult
    import time

    class Stream:
        def __init__(self):
            self.remaining = 5
        def __enter__(self):
            return self
        def __exit__(self, *_args):
            return None
        def read(self, _size):
            if not self.remaining:
                return b""
            self.remaining -= 1
            return b"x" * 1024
    class Archive:
        def open(self, _info, _mode):
            return Stream()

    engine = ArchiveInspectionEngine(ArchiveLimits(
        max_entries=100, max_total_uncompressed_bytes=2000,
        max_entry_uncompressed_bytes=2000, max_compression_ratio=500,
        max_nesting_depth=2, timeout_seconds=10, chunk_size=1024, magic_read_bytes=64,
    ))
    entry = ArchiveEntry("ref", "data.bin", "data.bin", ".bin", 1, 100, 100, "0", 0, False, "file")
    result = ArchiveInspectionResult(entries=[entry])
    engine._stream_entry(Archive(), object(), entry, result, _Budget(time.monotonic() + 10), 0)
    assert entry.sha256 is None
    assert "archive_expansion_limit" in entry.inspection_flags


def test_timeout_yields_partial_result(monkeypatch, tmp_path):
    path = _zip(tmp_path / "timeout.zip", {"a.txt": b"a"})
    ticks = iter([0.0, 2.0, 2.0])
    monkeypatch.setattr("app.parsers.archive.time.monotonic", lambda: next(ticks, 2.0))
    result = _engine(timeout_seconds=1).inspect(path)
    assert result.state == "partial"
    assert "archive_timeout" in _flags(result)


def _identification(detected="ZIP"):
    return ArtifactIdentification(
        declared_extension=".zip", filename="evidence.zip", detected_type=detected,
        mime_type="application/zip" if detected == "ZIP" else "application/octet-stream",
        magic_signature="50 4B 03 04", extension_matches=True, confidence=90,
    )


def test_parser_registry_selects_zip_parser_by_detected_content(tmp_path):
    registry = ParserRegistry([ZipArtifactParser(_engine())])
    parser = registry.select(_identification())
    assert parser.parser_id == "archive_zip_v1"
    parsed = registry.parse(_zip(tmp_path / "renamed.pdf", {"a.txt": b"a"}), _identification())
    assert parsed.parser_id == "archive_zip_v1" and parsed.embedded_artifacts


def test_parser_registry_fallback_for_unknown_format(tmp_path):
    registry = ParserRegistry([ZipArtifactParser(_engine())])
    identification = _identification("UNKNOWN")
    identification = ArtifactIdentification(
        ".bin", "unknown.bin", "UNKNOWN", "application/octet-stream", "00", False
    )
    parsed = registry.parse(tmp_path / "unknown.bin", identification)
    assert parsed.parser_id == BinaryFallbackParser.parser_id
    assert parsed.limitations


def test_parser_registry_rejects_duplicate_ids():
    parser = ZipArtifactParser(_engine())
    registry = ParserRegistry([parser])
    with pytest.raises(ValueError, match="duplicado"):
        registry.register(parser)


def test_parser_failure_isolated_as_partial_contract(tmp_path):
    class Metadata:
        def extract_step(self, _path):
            return StepResult(
                "metadata_extraction", "metadata", ProcessingStatus.SUCCESS,
                "ok", "ok", value=MetadataResult({}),
            )

    class FailingParser:
        parser_id = "failing"
        supported_types = frozenset({"ZIP"})
        priority = 100
        def can_parse(self, identification):
            return identification.detected_type == "ZIP"
        def parse(self, path, identification):
            raise RuntimeError("internal parser detail")

    path = _zip(tmp_path / "failure.zip", {"a.txt": b"a"})
    analyzer = FileAnalyzer(
        hash_engine=HashEngine(), metadata_engine=Metadata(), findings_engine=FindingsEngine(),
        magic_number_engine=MagicNumberEngine(), digital_signature_engine=DigitalSignatureEngine(),
        pdf_structure_engine=PDFStructureEngine(), parser_registry=ParserRegistry([FailingParser()]),
    )
    result = analyzer.analyze_fixture(path)
    result.analysis_id = "archive-partial"
    contract = LegacyAnalysisAdapter().convert(result)
    assert contract.state is AnalysisState.PARTIAL
    assert any(step["code"] == "artifact_parsing" for step in contract.processing_steps)
    assert "internal parser detail" not in str(contract)


def test_archive_parser_creates_embedded_refs_not_jobs(tmp_path):
    parsed = ParserRegistry([ZipArtifactParser(_engine())]).parse(
        _zip(tmp_path / "one.zip", {"a.txt": b"a"}), _identification()
    )
    entry = parsed.embedded_artifacts[0]
    assert entry.embedded_artifact_ref
    assert not hasattr(entry, "job_id")


def test_synthetic_acceptance_archive(tmp_path):
    entries = {
        "contrato.pdf": b"%PDF-1.7\n%%EOF",
        "selfie.jpg": b"\xff\xd8\xffsynthetic",
        "dados.json": b'{"event": "synthetic"}',
        "script.js": b"// inert synthetic fixture",
        "setup.exe": b"MZsynthetic-not-executable-code",
        "documento.pdf.exe": b"MZsynthetic-not-executable-code",
    }
    result = _engine().inspect(_zip(tmp_path / "evidencias.zip", entries))
    by_name = {entry.filename: entry for entry in result.entries}
    assert by_name["contrato.pdf"].detected_type == "PDF"
    assert by_name["selfie.jpg"].detected_type == "JPEG"
    assert by_name["dados.json"].detected_type == "JSON"
    assert "script_content_detected" in by_name["script.js"].inspection_flags
    assert "executable_content_detected" in by_name["setup.exe"].inspection_flags
    assert "double_extension" in by_name["documento.pdf.exe"].inspection_flags
    assert result.total_entries == 6


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_entries": 0}, {"max_total_uncompressed_bytes": -1},
        {"max_entry_uncompressed_bytes": 0}, {"max_compression_ratio": 0},
        {"max_nesting_depth": 21}, {"timeout_seconds": 0},
    ],
)
def test_invalid_archive_config_is_rejected(kwargs):
    values = dict(
        max_entries=10, max_total_uncompressed_bytes=1000,
        max_entry_uncompressed_bytes=500, max_compression_ratio=10,
        max_nesting_depth=2, timeout_seconds=10,
    )
    values.update(kwargs)
    with pytest.raises(ValueError):
        ArchiveLimits(**values).validate()

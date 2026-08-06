from __future__ import annotations

import hashlib
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest

from app.engines.file_analyzer import FileAnalyzer
from app.engines.hash_engine import HashEngine
from app.evidence import (
    CaptureState,
    EvidenceAcquisitionError,
    EvidenceIntegrityError,
    EvidenceManager,
)
from app.models import (
    DigitalSignatureResult,
    MagicNumberResult,
    MetadataResult,
)
from app.services.analysis_service import AnalysisService
from app.services.timeline_service import TimelineService


def test_acquisition_rejects_missing_file_and_directory(tmp_path: Path) -> None:
    manager = EvidenceManager(tmp_path / "work")

    with pytest.raises(EvidenceAcquisitionError, match="não encontrado"):
        manager.acquire(tmp_path / "missing.bin")
    with pytest.raises(EvidenceAcquisitionError, match="não representa um arquivo"):
        manager.acquire(tmp_path)


@pytest.mark.parametrize(
    ("name", "content"),
    [
        ("vazio.bin", b""),
        ("evidência com acentos.bin", "conteúdo técnico".encode()),
    ],
)
def test_empty_and_unicode_files_are_acquired_and_verified(
    tmp_path: Path,
    name: str,
    content: bytes,
) -> None:
    original = tmp_path / name
    original.write_bytes(content)
    manager = EvidenceManager(tmp_path / "work")

    with manager.acquire(original) as lease:
        source = lease.source
        verified = lease.verify()

        assert source.original_name == name
        assert source.size_bytes == len(content)
        assert source.initial_sha256 == hashlib.sha256(content).hexdigest()
        assert verified.final_sha256 == source.initial_sha256
        assert verified.capture_state is CaptureState.VERIFIED
        assert verified.acquired_at_utc.utcoffset() is not None
        assert verified.read_only is True
        assert source.working_path.stat().st_mode & (
            stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
        ) == 0

    assert not source.working_path.exists()
    assert original.read_bytes() == content


def test_change_after_acquisition_marks_source_compromised(tmp_path: Path) -> None:
    original = tmp_path / "evidence.bin"
    original.write_bytes(b"initial")
    manager = EvidenceManager(tmp_path / "work")

    with manager.acquire(original) as lease:
        original.write_bytes(b"changed")
        verified = lease.verify()

        assert verified.capture_state is CaptureState.COMPROMISED
        assert verified.initial_sha256 == verified.final_sha256
        assert any("original foi alterado" in error for error in verified.acquisition_errors)


def test_replacement_after_acquisition_is_detected_by_identity(tmp_path: Path) -> None:
    original = tmp_path / "evidence.bin"
    original.write_bytes(b"same bytes")
    replacement = tmp_path / "replacement.bin"
    replacement.write_bytes(b"same bytes")
    manager = EvidenceManager(tmp_path / "work")

    with manager.acquire(original) as lease:
        original.unlink()
        replacement.replace(original)
        verified = lease.verify()

        assert verified.capture_state is CaptureState.COMPROMISED
        assert any("identidade" in error for error in verified.acquisition_errors)


def test_simultaneous_acquisitions_are_isolated_even_with_same_name(
    tmp_path: Path,
) -> None:
    left = tmp_path / "left" / "same.bin"
    right = tmp_path / "right" / "same.bin"
    left.parent.mkdir()
    right.parent.mkdir()
    left.write_bytes(b"left")
    right.write_bytes(b"right")
    manager = EvidenceManager(tmp_path / "work")
    barrier = Barrier(2)

    def acquire(path: Path) -> tuple[str, Path, bytes]:
        with manager.acquire(path) as lease:
            barrier.wait(timeout=5)
            return (
                lease.source.evidence_id,
                lease.source.working_path,
                lease.source.working_path.read_bytes(),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(acquire, (left, right)))

    assert results[0][0] != results[1][0]
    assert results[0][1].parent != results[1][1].parent
    assert {results[0][2], results[1][2]} == {b"left", b"right"}
    assert not results[0][1].exists()
    assert not results[1][1].exists()


def test_derivatives_are_separate_and_name_collisions_are_rejected(
    tmp_path: Path,
) -> None:
    original = tmp_path / "source" / "evidence.bin"
    original.parent.mkdir()
    original.write_bytes(b"original")
    manager = EvidenceManager(tmp_path / "controlled" / "work")

    with manager.acquire(original) as lease:
        derived = lease.derivative_path("page-1.png")
        derived.write_bytes(b"derived")

        assert original.parent not in derived.parents
        with pytest.raises(FileExistsError):
            lease.derivative_path("page-1.png")
        with pytest.raises(ValueError):
            lease.derivative_path("../escape.bin")

    assert original.read_bytes() == b"original"
    assert not derived.exists()


def test_cleanup_occurs_after_failure(tmp_path: Path) -> None:
    original = tmp_path / "evidence.bin"
    original.write_bytes(b"original")
    manager = EvidenceManager(tmp_path / "work")
    working_path: Path | None = None

    with pytest.raises(RuntimeError, match="controlled"):
        with manager.acquire(original) as lease:
            working_path = lease.source.working_path
            raise RuntimeError("controlled")

    assert working_path is not None and not working_path.exists()
    assert original.read_bytes() == b"original"


class _Recorder:
    def __init__(self) -> None:
        self.paths: list[Path] = []

    def record(self, path: Path) -> None:
        self.paths.append(Path(path))


class _Hash(_Recorder):
    def __init__(self, after_hash=None) -> None:
        super().__init__()
        self.after_hash = after_hash

    def calculate_all(self, path: Path):
        self.record(path)
        result = HashEngine().calculate_all(path)
        if self.after_hash is not None:
            self.after_hash()
        return result


class _Metadata(_Recorder):
    def extract(self, path: Path):
        self.record(path)
        return MetadataResult(raw={"SourceFile": str(path)})


class _Magic(_Recorder):
    def analyze(self, path: Path):
        self.record(path)
        return MagicNumberResult(
            detected_type="PDF",
            detected_format="PDF",
            signature="25504446",
            extension_matches=False,
        )


class _Signature(_Recorder):
    def analyze(self, path: Path):
        self.record(path)
        return DigitalSignatureResult(has_signature=False)


class _Pdf(_Recorder):
    def analyze(self, path: Path):
        self.record(path)
        return SimpleNamespace(
            header_valid=True,
            eof_valid=True,
            eof_count=1,
            encrypted=False,
            javascript_detected=False,
            embedded_files=False,
            xref_found=True,
            trailer_found=True,
            incremental_updates=0,
        )


class _Json(_Recorder):
    def parse(self, path: Path):
        self.record(path)
        return SimpleNamespace(is_valid=True)


class _Biometric(_Recorder):
    def parse(self, path: Path):
        self.record(path)
        return None


class _Binary(_Recorder):
    def analyze(self, path: Path):
        self.record(path)
        return None


class _Text(_Recorder):
    def extract_text(self, path: Path) -> str:
        self.record(path)
        return "texto extraído da cópia controlada"


class _Findings:
    def analyze(self, **_kwargs):
        return []


def _service(
    tmp_path: Path,
    *,
    after_hash=None,
) -> tuple[AnalysisService, list[_Recorder]]:
    components: list[_Recorder] = [
        _Hash(after_hash),
        _Metadata(),
        _Magic(),
        _Signature(),
        _Pdf(),
        _Json(),
        _Biometric(),
        _Binary(),
        _Text(),
    ]
    analyzer = FileAnalyzer(
        hash_engine=components[0],
        metadata_engine=components[1],
        findings_engine=_Findings(),
        magic_number_engine=components[2],
        digital_signature_engine=components[3],
        pdf_structure_engine=components[4],
        json_parser_service=components[5],
        biometric_report_service=components[6],
        binary_structure_engine=components[7],
    )
    return (
        AnalysisService(
            analyzer,
            text_extraction_service=components[8],
            evidence_manager=EvidenceManager(tmp_path / "work"),
        ),
        components,
    )


def test_all_migrated_file_consumers_receive_one_controlled_copy(
    tmp_path: Path,
) -> None:
    original = tmp_path / "document.json"
    original.write_bytes(b'{"technical": true}')
    service, components = _service(tmp_path)

    result = service.analyze(original)

    observed = [path for component in components for path in component.paths]
    assert len(observed) == len(components)
    assert len(set(observed)) == 1
    assert observed[0] != original
    assert observed[0].name == original.name
    assert result.file_info.path == original.resolve()
    assert result.evidence_source is not None
    assert result.evidence_source.capture_state is CaptureState.VERIFIED
    assert result.hashes.sha256 == result.evidence_source.initial_sha256
    assert result.evidence_source.final_sha256 == result.evidence_source.initial_sha256
    assert not result.evidence_source.working_path.exists()


def test_original_replaced_during_analysis_blocks_partial_result(
    tmp_path: Path,
) -> None:
    original = tmp_path / "document.json"
    original.write_bytes(b'{"technical": true}')

    def replace_original() -> None:
        replacement = tmp_path / "replacement.json"
        replacement.write_bytes(b'{"other": true}')
        original.unlink()
        replacement.replace(original)

    service, components = _service(tmp_path, after_hash=replace_original)

    with pytest.raises(EvidenceIntegrityError) as captured:
        service.analyze(original)

    error = captured.value
    assert error.evidence.capture_state is CaptureState.COMPROMISED
    assert error.partial_result is not None
    assert error.partial_result.evidence_source is error.evidence
    assert not error.evidence.working_path.exists()
    observed = [path for component in components for path in component.paths]
    assert len(set(observed)) == 1


def test_timeline_reuses_captured_text_without_reopening_original(
    tmp_path: Path,
) -> None:
    original = tmp_path / "document.json"
    original.write_bytes(b'{"technical": true}')
    service, _components = _service(tmp_path)
    result = service.analyze(original)
    timeline = TimelineService()

    class _MustNotRead:
        def extract_text(self, _path: Path) -> str:
            raise AssertionError("Timeline não deve reabrir a evidência")

    timeline.text_service = _MustNotRead()
    events, _summary = timeline.build_timeline(result)

    assert events

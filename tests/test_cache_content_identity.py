from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import os
from pathlib import Path

import pytest

from app.evidence import CaptureState, EvidenceSource, FileIdentity
from app.models import (
    AnalysisResult,
    DigitalSignatureResult,
    FileInfo,
    HashResult,
    MagicNumberResult,
    MetadataResult,
)
from app.models.integrity_result import IntegrityResult
from app.observability import ObservabilityService
from app.workers.analysis_worker import AnalysisWorker


def _result_for(path: Path, payload: bytes) -> AnalysisResult:
    stat = path.stat()
    digest = sha256(payload).hexdigest()
    source = EvidenceSource(
        evidence_id=f"evidence-{digest[:12]}",
        original_name=path.name,
        original_path=path.resolve(),
        working_path=path.resolve(),
        size_bytes=len(payload),
        initial_sha256=digest,
        acquired_at_utc=datetime.now(timezone.utc),
        declared_type=path.suffix or "sem_extensao",
        detected_type=None,
        capture_state=CaptureState.VERIFIED,
        read_only=True,
        acquisition_errors=(),
        original_identity=FileIdentity.from_stat(stat),
        final_sha256=digest,
    )
    return AnalysisResult(
        file_info=FileInfo(
            path.name,
            path.resolve(),
            path.suffix,
            len(payload),
            modified_at=datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc),
        ),
        hashes=HashResult("", "", "", digest, "", ""),
        metadata=MetadataResult({"fixture": payload.decode("ascii")}),
        findings=[],
        magic_numbers=MagicNumberResult("UNKNOWN", "", False),
        digital_signature=DigitalSignatureResult(False),
        integrity=IntegrityResult(None, "Technical fixture", None, True, False, False),
        evidence_source=source,
    )


class _ContentService:
    def __init__(self) -> None:
        self.analyzed_payloads: list[bytes] = []
        self.correlations: list[tuple[str, tuple[AnalysisResult, ...]]] = []
        self.worker: AnalysisWorker | None = None
        self.cancel_during_analysis = False

    def analyze(self, path: Path, *, analysis_id: str) -> AnalysisResult:
        payload = path.read_bytes()
        self.analyzed_payloads.append(payload)
        result = _result_for(path, payload)
        result.analysis_id = analysis_id
        if self.cancel_during_analysis and self.worker is not None:
            self.worker.cancel()
        return result

    def correlate_case(self, case_id: str, results: list[AnalysisResult]):
        self.correlations.append((case_id, tuple(results)))
        return None

    def correlate_case_canonical(self, _case_id: str, _results: list[AnalysisResult]):
        return None


def _run(
    path: Path,
    *,
    cached: AnalysisResult | None = None,
    case_id: str = "case-a",
    service: _ContentService | None = None,
    observability: ObservabilityService | None = None,
) -> tuple[_ContentService, list[AnalysisResult], ObservabilityService]:
    active_service = service or _ContentService()
    metrics = observability or ObservabilityService()
    case_ref = metrics.begin_case(case_id, [(str(path), path.stat().st_size)], 0.0)
    worker = AnalysisWorker(
        analysis_service=active_service,
        files=[path],
        case_id=case_id,
        cached_results=({str(path.resolve()): cached} if cached is not None else None),
        observability=metrics,
    )
    active_service.worker = worker
    worker.case_ref = case_ref
    completed: list[list[AnalysisResult]] = []
    worker.completed.connect(completed.append)
    worker.run()
    return active_service, completed[0], metrics


def test_unchanged_bytes_are_a_cache_hit(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    cached = _result_for(path, b"AAAA")

    service, results, metrics = _run(path, cached=cached)

    assert service.analyzed_payloads == []
    assert results[0].hashes.sha256 == sha256(b"AAAA").hexdigest()
    assert results[0] is not cached
    results[0].metadata.raw["consumer_mutation"] = True
    assert "consumer_mutation" not in cached.metadata.raw
    assert metrics.snapshot().case_performance.cache_hits == 1


@pytest.mark.parametrize(
    ("replacement", "restore_mtime"),
    [(b"BBBBBB", False), (b"BBBB", False), (b"BBBB", True)],
    ids=["different-size", "same-size", "same-size-restored-mtime"],
)
def test_changed_bytes_are_a_cache_miss(
    tmp_path: Path, replacement: bytes, restore_mtime: bool,
) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    original_stat = path.stat()
    cached = _result_for(path, b"AAAA")
    path.write_bytes(replacement)
    if restore_mtime:
        os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    service, results, metrics = _run(path, cached=cached)

    assert service.analyzed_payloads == [replacement]
    assert results[0].hashes.sha256 == sha256(replacement).hexdigest()
    assert results[0].hashes.sha256 != cached.hashes.sha256
    assert metrics.snapshot().case_performance.cache_misses == 1


@pytest.mark.parametrize("identity_state", ["missing", "malformed", "mismatch"])
def test_unprovable_cached_identity_fails_safe(
    tmp_path: Path, identity_state: str,
) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    cached = _result_for(path, b"AAAA")
    if identity_state == "missing":
        cached.evidence_source = None
    elif identity_state == "malformed":
        cached.evidence_source = replace(cached.evidence_source, initial_sha256="invalid")
    else:
        cached.evidence_source = replace(cached.evidence_source, final_sha256="b" * 64)

    service, results, metrics = _run(path, cached=cached)

    assert service.analyzed_payloads == [b"AAAA"]
    assert results[0] is not cached
    assert metrics.snapshot().case_performance.cache_misses == 1


def test_cache_disabled_preserves_normal_analysis(tmp_path: Path) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")

    service, results, metrics = _run(path)

    assert service.analyzed_payloads == [b"AAAA"]
    assert results[0].hashes.sha256 == sha256(b"AAAA").hexdigest()
    assert metrics.snapshot().case_performance.cache_misses == 1


def test_identity_calculation_failure_is_a_safe_miss(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    cached = _result_for(path, b"AAAA")
    monkeypatch.setattr(
        "app.workers.analysis_worker.EvidenceContentIdentity.calculate",
        lambda _path: None,
    )

    service, results, metrics = _run(path, cached=cached)

    assert service.analyzed_payloads == [b"AAAA"]
    assert results[0] is not cached
    assert metrics.snapshot().case_performance.cache_misses == 1


def test_same_bytes_at_a_different_path_do_not_reuse_stale_provenance(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"AAAA")
    second.write_bytes(b"AAAA")
    cached = _result_for(first, b"AAAA")

    service, results, metrics = _run(second, cached=cached)

    assert service.analyzed_payloads == [b"AAAA"]
    assert results[0].file_info.path == second.resolve()
    assert results[0].evidence_source.original_path == second.resolve()
    assert metrics.snapshot().case_performance.cache_misses == 1


def test_cancellation_after_identity_mismatch_never_returns_stale_result(
    tmp_path: Path,
) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    cached = _result_for(path, b"AAAA")
    path.write_bytes(b"BBBB")
    service = _ContentService()
    service.cancel_during_analysis = True

    service, results, metrics = _run(path, cached=cached, service=service)

    assert service.analyzed_payloads == [b"BBBB"]
    assert results == []
    assert metrics.snapshot().case_performance.cache_hits == 0


def test_same_artifact_in_two_cases_rebuilds_case_correlation(
    tmp_path: Path,
) -> None:
    path = tmp_path / "artifact.bin"
    path.write_bytes(b"AAAA")
    cached = _result_for(path, b"AAAA")
    service = _ContentService()

    _run(path, cached=cached, case_id="case-a", service=service)
    _run(path, cached=cached, case_id="case-b", service=service)

    assert [case_id for case_id, _results in service.correlations] == ["case-a", "case-b"]
    assert all(results[0].hashes.sha256 == cached.hashes.sha256 for _, results in service.correlations)

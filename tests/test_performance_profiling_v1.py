from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from hashlib import sha256
import json
from types import SimpleNamespace

import pytest

from app.correlation.v2.pipeline import CanonicalCasePipeline
from app.engines.hash_engine import HashEngine
from app.models import (
    AnalysisResult,
    FileInfo,
    HashResult,
    MetadataResult,
    MagicNumberResult,
    DigitalSignatureResult,
)
from app.models.integrity_result import IntegrityResult
from app.observability import (
    ObservabilityService,
    ExecutionMetric,
    ExecutionStatus,
    diagnostic_payload,
)
from app.observability.models import CorrelationRuleMetric, MeasurementState, PerformanceMilestone
from app.observability.profiling import ProfilingBinding, profile_call, profiling_scope
from app.processing import ProcessingStatus, StepResult
from app.workers.analysis_worker import AnalysisWorker
from app.evidence import CaptureState, EvidenceSource, FileIdentity

NOW = datetime.now(timezone.utc)


def result_for(path, *, useful=True):
    result = AnalysisResult(
        file_info=FileInfo(path.name, path, path.suffix, 4),
        hashes=HashResult("", "", "", "a" * 64 if useful else "", "", ""),
        metadata=MetadataResult({}),
        findings=[],
        magic_numbers=MagicNumberResult("UNKNOWN", "", False),
        digital_signature=DigitalSignatureResult(False),
        integrity=IntegrityResult(None, "Technical fixture", None, useful, False, False),
        analysis_id="fixture",
    )
    if useful and path.exists():
        stat = path.stat()
        digest = sha256(path.read_bytes()).hexdigest()
        result.hashes = HashResult("", "", "", digest, "", "")
        result.evidence_source = EvidenceSource(
            evidence_id=f"fixture-{digest[:12]}",
            original_name=path.name,
            original_path=path.resolve(),
            working_path=path.resolve(),
            size_bytes=stat.st_size,
            initial_sha256=digest,
            acquired_at_utc=NOW,
            declared_type=path.suffix or "sem_extensao",
            detected_type=None,
            capture_state=CaptureState.VERIFIED,
            read_only=True,
            acquisition_errors=(),
            original_identity=FileIdentity.from_stat(stat),
            final_sha256=digest,
        )
    return result


def finish(service, **extra):
    service.update_case(
        completed=1,
        partial=0,
        failed=0,
        pending=0,
        running=0,
        cache_hits=0,
        cache_misses=1,
        finished=True,
        **extra,
    )


def test_monotonic_ttfr_total_cpu_and_finish_are_immutable(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.observability.service.perf_counter", lambda: clock[0])
    monkeypatch.setattr("app.observability.service.process_time", lambda: clock[0] / 2)
    service = ObservabilityService()
    service.begin_case("case", [("a", 4)], 0)
    clock[0] = 0.620
    service.update_case(
        completed=1,
        partial=0,
        failed=0,
        pending=0,
        running=0,
        cache_hits=0,
        cache_misses=1,
        first_result=True,
    )
    first_snapshot = service.snapshot()
    clock[0] = 18.4
    finish(service)
    case = service.snapshot().case_performance
    assert case.first_result_ms == pytest.approx(620)
    assert case.total_analysis_ms == pytest.approx(18_400)
    assert case.case_cpu_ms == pytest.approx(9_200)
    assert case.cpu_state is MeasurementState.PARTIAL
    assert all((case.case_started_at, case.first_useful_result_at, case.case_finished_at))
    clock[0] = 30
    finish(service, first_result=True)
    assert service.snapshot().case_performance == case
    assert first_snapshot.case_performance.total_analysis_ms is None
    with pytest.raises(FrozenInstanceError):
        case.first_result_ms = 0


def test_new_session_does_not_include_previous_measurements():
    service = ObservabilityService()
    old_ref = service.begin_case("old", [("a", 4)], 0)
    service.record_metric(
        ExecutionMetric(
            "old",
            "ocr",
            NOW,
            duration_ms=20,
            case_ref=old_ref,
            status=ExecutionStatus.COMPLETED,
            bytes_read=10,
        )
    )
    old = service.snapshot()
    service.begin_case("new", [("b", 8)], 0)
    current = service.snapshot()
    assert not current.engine_metrics and not current.execution_metrics
    assert current.io_stats.measured_engine_reads is None
    assert current.case_performance.session_id != old.case_performance.session_id
    assert old.engine_metrics[0].total_duration_ms == 20


def test_real_hash_reads_are_measured_even_for_empty_file(tmp_path):
    for size in (0, 2_100_000):
        path = tmp_path / "synthetic.bin"
        path.write_bytes(b"x" * size)
        service = ObservabilityService()
        ref = service.begin_case("case", [(str(path), size)], 0)
        with profiling_scope(ProfilingBinding(service, ref, "file_safe", size)):
            result = profile_call("hash", "hash", HashEngine().calculate_all, path)
        snapshot = service.snapshot()
        assert len(result.sha256) == 64
        assert snapshot.io_stats.measured_engine_reads == size
        assert snapshot.io_stats.state is MeasurementState.PARTIAL
        assert snapshot.execution_metrics[0].cpu_duration_ms is None
        assert snapshot.execution_metrics[0].duration_ms >= 0


def test_operation_clock_measures_callable_and_restores_scope(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.observability.profiling.perf_counter", lambda: clock[0])
    service = ObservabilityService()

    def parser():
        clock[0] += 0.042
        return StepResult(
            "parse", "parser", ProcessingStatus.SUCCESS, "done", "done", value={"private": "value"}
        )

    with profiling_scope(ProfilingBinding(service, None, "file_safe")):
        value = profile_call("parser", "artifact_parsing", parser)
    assert value.value == {"private": "value"}
    assert service.snapshot().engine_metrics[0].total_duration_ms == pytest.approx(42)
    profile_call("parser", "artifact_parsing", parser)
    assert service.snapshot().engine_metrics[0].executions == 1
    assert "private" not in json.dumps(diagnostic_payload(service.snapshot()))


def test_observability_exception_preserves_original_return_and_error():
    class Broken:
        def record_metric(self, _):
            raise RuntimeError("collector failed")

    with profiling_scope(ProfilingBinding(Broken(), None, None)):
        assert profile_call("test", "call", lambda: 42) == 42

        def fail():
            raise ValueError("original")

        with pytest.raises(ValueError, match="original"):
            profile_call("test", "call", fail)


def test_failed_and_skipped_operations_have_correct_counts():
    service = ObservabilityService()
    with profiling_scope(ProfilingBinding(service, None, "file_safe")):
        with pytest.raises(OSError):
            profile_call("parser", "parse", lambda: (_ for _ in ()).throw(OSError("private")))
        profile_call(
            "parser",
            "parse",
            lambda: StepResult("parse", "parser", ProcessingStatus.SKIPPED, "skip", "skip"),
        )
    engine = service.snapshot().engine_metrics[0]
    assert (engine.executions, engine.failures, engine.cancelled) == (1, 1, 0)


def test_unavailable_is_distinct_and_an_earlier_failure_is_not_erased():
    service = ObservabilityService()
    with profiling_scope(ProfilingBinding(service, None, "file_safe")):
        profile_call(
            "parser",
            "parse",
            lambda: StepResult(
                "parse", "parser", ProcessingStatus.UNAVAILABLE, "unavailable", "unavailable"
            ),
        )
        with pytest.raises(ValueError):
            profile_call(
                "parser", "parse", lambda: (_ for _ in ()).throw(ValueError("private"))
            )
        profile_call(
            "parser",
            "parse",
            lambda: StepResult("parse", "parser", ProcessingStatus.SUCCESS, "ok", "ok", value=1),
        )
    engine = service.snapshot().engine_metrics[0]
    assert engine.unavailable == 1
    assert engine.failures == 1
    assert engine.status.value == "ERROR"


def test_no_missing_duration_cpu_bytes_or_cache_rate_becomes_zero():
    service = ObservabilityService()
    service.begin_case("case", [("a", 4)], 0)
    service.record_metric(ExecutionMetric("x", "parser", NOW, status=ExecutionStatus.COMPLETED))
    snapshot = service.snapshot()
    engine = snapshot.engine_metrics[0]
    assert engine.executions == 1
    assert engine.total_duration_ms is None and engine.average_duration_ms is None
    assert engine.cpu_total_ms is None and engine.state is MeasurementState.UNAVAILABLE
    assert snapshot.cache_stats[0].hit_rate is None
    assert snapshot.io_stats.measured_engine_reads is None
    assert snapshot.io_stats.temporary_bytes_written is None


def test_bounded_samples_do_not_truncate_engine_totals_or_measured_reads():
    service = ObservabilityService(max_metrics=2)
    service.begin_case("case", [("a", 4)], 0)
    for index in range(200):
        service.record_metric(
            ExecutionMetric(
                f"m_{index}",
                "hash",
                NOW,
                duration_ms=index,
                status=ExecutionStatus.COMPLETED,
                bytes_read=4,
                file_ref="file_safe",
            )
        )
    snapshot = service.snapshot()
    engine = snapshot.engine_metrics[0]
    assert len(snapshot.execution_metrics) == 2
    assert snapshot.dropped_execution_samples == 198
    assert (engine.executions, engine.total_duration_ms) == (200, sum(range(200)))
    assert engine.median_sample_count == 128
    assert len(snapshot.slowest_executions) == 5
    assert snapshot.io_stats.measured_engine_reads == 800


def test_artifact_wall_is_not_sum_of_overlapping_stages():
    service = ObservabilityService()
    for engine, duration in (("analysis_pipeline", 100), ("text_extraction", 90), ("ocr", 80)):
        service.record_metric(
            ExecutionMetric(
                engine,
                engine,
                NOW,
                duration_ms=duration,
                status=ExecutionStatus.COMPLETED,
                file_ref="file_safe",
            )
        )
    artifact = service.snapshot().artifact_metrics[0]
    assert artifact.total_duration_ms == 100
    assert artifact.stage_wall_ms == 170
    assert len(artifact.stages) == 2
    assert artifact.slowest_stage == "text_extraction"


def test_unknown_artifact_wall_remains_null_with_stage_data():
    service = ObservabilityService()
    service.record_metric(
        ExecutionMetric(
            "x", "ocr", NOW, duration_ms=12, status=ExecutionStatus.COMPLETED, file_ref="file_safe"
        )
    )
    artifact = service.snapshot().artifact_metrics[0]
    assert artifact.total_duration_ms is None and artifact.stage_wall_ms == 12
    assert artifact.state is MeasurementState.PARTIAL


def test_empty_or_status_only_results_are_not_useful(tmp_path):
    result = result_for(tmp_path / "a.txt", useful=False)
    for state in ProcessingStatus:
        result.processing_steps = [StepResult("x", "x", state, "status only", "status only")]
        assert not AnalysisWorker._is_useful_result(result)
    assert AnalysisWorker._is_useful_result(result_for(tmp_path / "a.txt"))


def test_partial_typed_technical_payload_qualifies_for_ttfr(tmp_path):
    result = result_for(tmp_path / "a.bin", useful=False)
    result.processing_steps = [
        StepResult(
            "magic_number",
            "magic_number",
            ProcessingStatus.PARTIAL,
            "partial",
            "partial",
            value=MagicNumberResult("PDF", "25 50 44 46", True),
        )
    ]
    assert AnalysisWorker._is_useful_result(result)


def test_error_before_first_valid_result_across_multiple_files_sets_ttfr(tmp_path):
    first = tmp_path / "first.bin"
    second = tmp_path / "second.bin"
    first.write_bytes(b"bad!")
    second.write_bytes(b"good")

    class Service:
        def analyze(self, path, **_):
            if path == first:
                raise OSError("private failure")
            return result_for(path)

        def correlate(self, _):
            return None

    service = ObservabilityService()
    ref = service.begin_case("case", [(str(first), 4), (str(second), 4)], 0)
    worker = AnalysisWorker(analysis_service=Service(), files=[first, second], observability=service)
    worker.case_ref = ref
    worker.run()
    case = service.snapshot().case_performance
    assert case.first_result_ms is not None
    assert case.failed == 1
    assert case.state is ExecutionStatus.PARTIAL


def test_session_without_a_valid_result_keeps_ttfr_unavailable(tmp_path):
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")

    class Service:
        def analyze(self, path, **_):
            return result_for(path, useful=False)

        def correlate(self, _):
            return None

    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 0)], 0)
    worker = AnalysisWorker(analysis_service=Service(), files=[path], observability=service)
    worker.case_ref = ref
    worker.run()
    assert service.snapshot().case_performance.first_result_ms is None


def test_worker_marks_ttfr_before_legacy_correlation_and_sending_result(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr("app.observability.service.perf_counter", lambda: clock[0])
    monkeypatch.setattr("app.observability.profiling.perf_counter", lambda: clock[0])
    monkeypatch.setattr("app.workers.analysis_worker.perf_counter", lambda: clock[0])
    path = tmp_path / "a.txt"
    path.write_bytes(b"test")

    class Service:
        def analyze(self, path, **_):
            def run():
                clock[0] += 0.2
                return result_for(path)

            return profile_call("parser", "artifact_parsing", run)

        def correlate_case(self, _, results):
            if results:
                clock[0] += 5
            return None

        def correlate_case_canonical(self, _, results):
            return CanonicalCasePipeline().analyze("case", results)

    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 4)], 0)
    worker = AnalysisWorker(
        analysis_service=Service(), files=[path], case_id="case", observability=service
    )
    worker.case_ref = ref
    observed = []
    worker.file_analyzed.connect(
        lambda _: observed.append(service.snapshot().case_performance.first_result_ms)
    )
    worker.run()
    case = service.snapshot().case_performance
    assert observed == [pytest.approx(200)]
    assert case.first_result_ms == pytest.approx(200)
    assert case.total_analysis_ms == pytest.approx(5200)
    names = [item.name for item in case.milestones]
    assert names.index("all_artifacts_processed") < names.index("correlation_completed")
    assert names.index("correlation_started") < names.index("correlation_completed")


def test_40_artifact_case_records_one_final_legacy_recomputation(tmp_path):
    paths = [tmp_path / f"artifact-{index:02d}.bin" for index in range(40)]
    for path in paths:
        path.write_bytes(b"data")

    class Service:
        def analyze(self, path, **_):
            return result_for(path)

        def correlate_case(self, _, results):
            return tuple(result.analysis_id for result in results)

    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 4) for path in paths], 0)
    worker = AnalysisWorker(
        analysis_service=Service(), files=paths, case_id="case", observability=service
    )
    worker.case_ref = ref
    worker.run()

    snapshot = service.snapshot()
    legacy = next(item for item in snapshot.engine_metrics if item.engine_id == "legacy_correlation")
    assert legacy.executions == 1
    assert legacy.total_duration_ms is not None and legacy.total_duration_ms >= 0
    assert snapshot.case_performance.first_result_ms is not None
    assert snapshot.case_performance.total_analysis_ms is not None


def test_cached_worker_consumes_queue_without_fake_engine_calls(tmp_path):
    path = tmp_path / "cached.txt"
    path.write_bytes(b"test")
    cached = result_for(path)
    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 4)], 0, cache_entries=1)
    worker = AnalysisWorker(
        analysis_service=SimpleNamespace(correlate=lambda _: None),
        files=[path],
        cached_results={str(path.resolve()): cached},
        observability=service,
    )
    worker.case_ref = ref
    worker.run()
    snapshot = service.snapshot()
    assert (snapshot.queue_stats.queue_depth, snapshot.queue_stats.completed_jobs) == (0, 1)
    assert snapshot.cache_stats[0].hit_rate == 1
    assert snapshot.case_performance.first_result_ms is not None
    assert {item.engine_id for item in snapshot.engine_metrics} == {
        "analysis_cache",
        "legacy_correlation",
    }
    assert snapshot.io_stats.measured_engine_reads is None


def test_partial_failed_and_unavailable_cache_reuse_is_not_a_completed_cache_hit(tmp_path):
    path = tmp_path / "cached.txt"
    path.write_bytes(b"test")
    for status in (
        ProcessingStatus.PARTIAL,
        ProcessingStatus.FAILED,
        ProcessingStatus.UNAVAILABLE,
        ProcessingStatus.LIMIT_EXCEEDED,
    ):
        cached = result_for(path)
        cached.processing_steps = [StepResult("x", "x", status, "state", "state", value=1)]
        service = ObservabilityService()
        ref = service.begin_case("case", [(str(path), 4)], 0, cache_entries=1)
        worker = AnalysisWorker(
            analysis_service=SimpleNamespace(correlate=lambda _: None),
            files=[path],
            cached_results={str(path.resolve()): cached},
            observability=service,
        )
        worker.case_ref = ref
        worker.run()
        snapshot = service.snapshot()
        assert snapshot.case_performance.cache_hits == 1
        assert snapshot.cache_stats[0].hits == 0
        assert snapshot.cache_stats[0].hit_rate is None
        assert snapshot.engine_metrics[0].partial == 1


def test_cancelled_worker_keeps_stages_without_counting_failure(tmp_path):
    path = tmp_path / "a.txt"
    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 4), ("b", 4)], 0)

    class Service:
        def analyze(self, path, **_):
            value = profile_call("parser", "parse", lambda: result_for(path))
            worker.cancel()
            return value

    worker = AnalysisWorker(
        analysis_service=Service(), files=[path, tmp_path / "b.txt"], observability=service
    )
    worker.case_ref = ref
    worker.run()
    snapshot = service.snapshot()
    assert snapshot.case_performance.state is ExecutionStatus.CANCELLED
    assert snapshot.case_performance.first_result_ms is None
    assert snapshot.queue_stats.failed_jobs == 0 and snapshot.queue_stats.cancelled_jobs == 1
    assert (
        snapshot.queue_stats.cancelled_before_start == 1 and snapshot.queue_stats.queue_depth == 0
    )
    assert {item.engine_id for item in snapshot.engine_metrics} >= {"parser", "analysis_pipeline"}


def test_canonical_pipeline_reports_rule_failures_and_phase_times():
    class FailedRule:
        rule_id = "case.synthetic_rule"
        rule_version = "1"

        def evaluate(self, _):
            raise RuntimeError("sensitive input")

    result = CanonicalCasePipeline(rules=[FailedRule()]).analyze("case", [])
    profile = result.performance
    assert (
        profile.duration_ms >= profile.index_build_duration_ms + profile.rule_evaluation_duration_ms
    )
    assert profile.rules[0].failed and profile.rules[0].findings == 0
    assert profile.rules[0].duration_ms >= 0


def test_strong_export_omits_free_text_names_and_identifiers():
    service = ObservabilityService()
    secret = "Maria da Silva email@example.com 123.456.789-00 2001:db8::1 C:/Users/private/doc.pdf"
    service.record_error(
        component_id="parser",
        operation="parse",
        error_code="parse_failed",
        error=RuntimeError(secret),
    )
    service.record_metric(
        ExecutionMetric(
            "x", "parser", NOW, metadata={"reason": secret, "extension": secret, "size_bytes": 4}
        )
    )
    encoded = json.dumps(diagnostic_payload(service.snapshot()), ensure_ascii=False)
    for term in ("Maria", "email@example.com", "123.456", "2001:db8", "private", "Users"):
        assert term not in encoded
    assert "performance_schema_version" in encoded


def test_export_pseudonymizes_internal_correlation_rule_ids():
    service = ObservabilityService()
    service.record_correlation(
        facts=0,
        occurrences=0,
        relations=0,
        duration_ms=1,
        index_ms=0.2,
        rules_ms=0.3,
        rules=(
            CorrelationRuleMetric("case.internal_sensitive_rule", 0.3, 0),
        ),
    )
    encoded = json.dumps(diagnostic_payload(service.snapshot()))
    assert "case.internal_sensitive_rule" not in encoded
    assert "rule_" in encoded


def test_negative_aggregate_durations_are_rejected():
    with pytest.raises(ValueError):
        CorrelationRuleMetric("rule", -1, 0)
    with pytest.raises(ValueError):
        PerformanceMilestone("event", -1)


def test_file_analyzer_measures_engine_boundary_without_step_timestamp_replay(
    tmp_path, monkeypatch
):
    from app.engines.file_analyzer import FileAnalyzer
    from app.engines.finding_engine import FindingsEngine
    from app.engines.magic_number_engine import MagicNumberEngine
    from app.engines.digital_signature_engine import DigitalSignatureEngine
    from app.engines.pdf_structure_engine import PDFStructureEngine

    clock = [0.0]
    monkeypatch.setattr("app.observability.profiling.perf_counter", lambda: clock[0])

    class Metadata:
        def extract_step(self, _):
            clock[0] += 0.070
            return StepResult(
                "metadata_extraction",
                "metadata",
                ProcessingStatus.SUCCESS,
                "done",
                "done",
                value=MetadataResult({}),
            )

    path = tmp_path / "fixture.txt"
    path.write_bytes(b"test")
    analyzer = FileAnalyzer(
        HashEngine(),
        Metadata(),
        FindingsEngine(),
        MagicNumberEngine(),
        DigitalSignatureEngine(),
        PDFStructureEngine(),
    )
    service = ObservabilityService()
    ref = service.begin_case("case", [(str(path), 4)], 0)
    with profiling_scope(ProfilingBinding(service, ref, "file_safe", 4)):
        result = analyzer.analyze_fixture(path)
    engines = {item.engine_id: item for item in service.snapshot().engine_metrics}
    assert engines["metadata"].total_duration_ms == pytest.approx(70)
    assert engines["metadata"].executions == 1
    assert engines["hash"].executions == 1
    assert service.snapshot().io_stats.measured_engine_reads == 4
    assert result.hashes.sha256
    assert "json" not in engines and "biometric" not in engines

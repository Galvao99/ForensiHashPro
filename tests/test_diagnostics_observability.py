from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.observability import (
    DIAGNOSTIC_SCHEMA_VERSION,
    PERFORMANCE_SCHEMA_VERSION,
    HealthCheckService,
    ObservabilityService,
    aggregate_system_health,
    diagnostic_payload,
    export_diagnostic,
)
from app.observability.models import (
    ActiveJob,
    ComponentHealth,
    ExecutionMetric,
    CorrelationRuleMetric,
    ExecutionStatus,
    MeasurementState,
    OperationalStatus,
)
from app.observability.sanitization import sanitize_message, safe_ref


NOW = datetime.now(timezone.utc)


def health(identifier, status, required=False):
    return ComponentHealth(identifier, identifier, status, NOW, required)


def test_operational_states_are_disjoint_from_epistemic_states():
    assert {item.value for item in OperationalStatus} == {"OK", "DEGRADED", "UNAVAILABLE", "ERROR"}
    assert not {"MATCH", "MISMATCH", "OBSERVED", "UNKNOWN", "NOT_APPLICABLE"} & {
        item.value for item in OperationalStatus
    }


def test_system_health_ok():
    assert (
        aggregate_system_health((health("core", OperationalStatus.OK, True),))
        is OperationalStatus.OK
    )


def test_required_degraded_degrades_system():
    assert (
        aggregate_system_health((health("core", OperationalStatus.DEGRADED, True),))
        is OperationalStatus.DEGRADED
    )


def test_optional_unavailable_does_not_break_system():
    items = (
        health("core", OperationalStatus.OK, True),
        health("ocr", OperationalStatus.UNAVAILABLE),
    )
    assert aggregate_system_health(items) is OperationalStatus.OK


def test_required_unavailable_is_error():
    assert (
        aggregate_system_health((health("core", OperationalStatus.UNAVAILABLE, True),))
        is OperationalStatus.ERROR
    )


def test_required_error_is_error():
    assert (
        aggregate_system_health((health("core", OperationalStatus.ERROR, True),))
        is OperationalStatus.ERROR
    )


def test_execution_metric_derives_duration():
    metric = ExecutionMetric(
        "x", "hash", NOW, NOW + timedelta(milliseconds=12), status=ExecutionStatus.COMPLETED
    )
    assert metric.duration_ms == 12


def test_recent_errors_are_bounded_and_sanitized():
    service = ObservabilityService(max_errors=2)
    for index in range(3):
        service.record_error(
            component_id="x",
            operation="read",
            error_code=str(index),
            error=f"C:\\secret\\person{index}.pdf 1.2.3.4",
        )
    errors = service.snapshot().recent_errors
    assert [item.error_code for item in errors] == ["1", "2"]
    assert all("secret" not in item.message and "1.2.3.4" not in item.message for item in errors)


def test_path_reference_is_stable_and_not_a_path():
    assert safe_ref("file", "C:\\Users\\Ana\\cpf.pdf") == safe_ref(
        "file", "C:\\Users\\Ana\\cpf.pdf"
    )
    assert "Ana" not in safe_ref("file", "C:\\Users\\Ana\\cpf.pdf")
    assert sanitize_message("/home/alice/document.pdf") == "[path]"


def test_case_timing_first_result_cache_and_counts():
    service = ObservabilityService()
    service.begin_case("sensitive", [("a", 10), ("b", 20)], 4.5)
    service.update_case(
        completed=1,
        partial=0,
        failed=0,
        pending=1,
        running=0,
        cache_hits=1,
        cache_misses=0,
        first_result=True,
    )
    service.update_case(
        completed=1,
        partial=0,
        failed=1,
        pending=0,
        running=0,
        cache_hits=1,
        cache_misses=1,
        finished=True,
    )
    case = service.snapshot().case_performance
    assert (
        case
        and case.ingestion_ms == 4.5
        and case.first_result_ms is not None
        and case.total_analysis_ms is not None
    )
    assert (case.cache_hits, case.cache_misses, case.failed) == (1, 1, 1)
    assert [item.name for item in case.milestones] == [
        "analysis_started",
        "first_useful_result",
        "all_artifacts_processed",
        "case_complete",
    ]


def test_engine_metrics_aggregate_failures_and_duration():
    service = ObservabilityService()
    service.record_metric(
        ExecutionMetric(
            "1", "ocr", NOW, NOW + timedelta(milliseconds=10), status=ExecutionStatus.COMPLETED
        )
    )
    service.record_metric(
        ExecutionMetric(
            "2", "ocr", NOW, NOW + timedelta(milliseconds=30), status=ExecutionStatus.FAILED
        )
    )
    metric = service.snapshot().engine_metrics[0]
    assert (metric.executions, metric.failures, metric.average_duration_ms, metric.status) == (
        2,
        1,
        20,
        OperationalStatus.ERROR,
    )


def test_jobs_do_not_invent_progress():
    service = ObservabilityService()
    job = service.start_job(
        case_ref=None, file_path="secret.pdf", engine_id="analysis_pipeline", operation="analyze"
    )
    assert service.snapshot().active_jobs[0].progress_percent is None
    service.finish_job(job)
    assert not service.snapshot().active_jobs


def test_job_accepts_real_progress_only_when_supplied():
    job = ActiveJob("x", ExecutionStatus.RUNNING, NOW, progress_percent=25)
    assert job.progress_percent == 25


def test_export_json_is_versioned_and_contains_no_forensic_payload(tmp_path):
    service = ObservabilityService()
    service.begin_case("Caso Maria", [("/secret/name.pdf", 4)], 1)
    destination = export_diagnostic(service.snapshot(), tmp_path / "diagnostic.json")
    payload = json.loads(destination.read_text(encoding="utf-8"))
    serialized = destination.read_text(encoding="utf-8")
    assert payload["diagnostic_schema_version"] == DIAGNOSTIC_SCHEMA_VERSION
    assert payload["performance_schema_version"] == PERFORMANCE_SCHEMA_VERSION
    assert "Caso Maria" not in serialized and "/secret/name.pdf" not in serialized
    assert not ({"evidence", "facts", "findings", "occurrences"} & {key.lower() for key in payload})


def test_error_is_only_operational_and_does_not_create_domain_objects():
    service = ObservabilityService()
    service.record_error(
        component_id="ocr", operation="run", error_code="ocr_failed", error=RuntimeError("failed")
    )
    payload = diagnostic_payload(service.snapshot())
    text = json.dumps(payload)
    assert "MATCH" not in text and "MISMATCH" not in text and "UNKNOWN" not in text
    assert "finding" not in text.lower() and "evidence" not in text.lower()


def test_thread_safe_collection():
    service = ObservabilityService(max_metrics=500)

    def add(index):
        service.record_metric(
            ExecutionMetric(str(index), "hash", NOW, NOW, status=ExecutionStatus.COMPLETED)
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(add, range(200)))
    assert service.snapshot().engine_metrics[0].executions == 200


def test_engine_and_artifact_profiling_are_aggregated_deterministically():
    service = ObservabilityService()
    service.record_metric(
        ExecutionMetric(
            "b",
            "ocr",
            NOW,
            NOW + timedelta(milliseconds=30),
            status=ExecutionStatus.COMPLETED,
            file_ref="file_b",
            operation="ocr",
            metadata={"size_bytes": 20},
        )
    )
    service.record_metric(
        ExecutionMetric(
            "a",
            "metadata",
            NOW,
            NOW + timedelta(milliseconds=10),
            status=ExecutionStatus.PARTIAL,
            file_ref="file_a",
            operation="metadata",
            metadata={"size_bytes": 10},
        )
    )
    snapshot = service.snapshot()
    assert [
        (item.engine_id, item.maximum_duration_ms, item.median_duration_ms)
        for item in snapshot.engine_metrics
    ] == [("metadata", 10, 10), ("ocr", 30, 30)]
    assert [item.artifact_ref for item in snapshot.artifact_metrics] == ["file_b", "file_a"]
    assert snapshot.artifact_metrics[1].status is ExecutionStatus.PARTIAL
    assert snapshot.engine_metrics[0].cpu_state is MeasurementState.UNAVAILABLE


def test_queue_peaks_and_cancelled_jobs_are_not_failures():
    service = ObservabilityService()
    service.begin_case("case", [("a", 1), ("b", 1)], 0)
    first = service.start_job(
        case_ref="case_x", file_path="a", engine_id="pipeline", operation="run"
    )
    second = service.start_job(
        case_ref="case_x", file_path="b", engine_id="pipeline", operation="run"
    )
    service.finish_job(first, ExecutionStatus.CANCELLED)
    service.finish_job(second, ExecutionStatus.FAILED)
    stats = service.snapshot().queue_stats
    assert (stats.peak_queue_depth, stats.peak_concurrency) == (2, 2)
    assert (stats.cancelled_jobs, stats.failed_jobs, stats.completed_jobs) == (1, 1, 0)


def test_correlation_stats_and_partial_measured_io():
    service = ObservabilityService()
    service.begin_case("case", [("a", 100)], 0)
    service.record_metric(
        ExecutionMetric(
            "io", "hash", NOW, status=ExecutionStatus.COMPLETED, file_ref="file_x", bytes_read=100
        )
    )
    service.record_correlation(
        facts=3,
        occurrences=4,
        relations=2,
        duration_ms=8,
        index_ms=1,
        rules_ms=5,
        rules=(CorrelationRuleMetric("rule.b", 3, 0), CorrelationRuleMetric("rule.a", 2, 1)),
    )
    snapshot = service.snapshot()
    assert snapshot.io_stats and snapshot.io_stats.state is MeasurementState.PARTIAL
    assert snapshot.io_stats.read_amplification == 1
    assert snapshot.correlation_stats and snapshot.correlation_stats.rules_producing_findings == 1
    assert [item.rule_id for item in snapshot.correlation_stats.rules] == ["rule.b", "rule.a"]


def test_cancelled_case_keeps_partial_metrics_and_missing_values_are_not_zero():
    service = ObservabilityService()
    service.begin_case("case", [("a", 1)], 0)
    service.update_case(
        completed=0,
        partial=0,
        failed=0,
        pending=1,
        running=0,
        cache_hits=0,
        cache_misses=0,
        finished=True,
        cancelled=True,
    )
    case = service.snapshot().case_performance
    assert case and case.state is ExecutionStatus.CANCELLED and case.total_analysis_ms is not None
    assert case.first_result_ms is None and case.correlation_duration_ms is None


def test_extended_sanitization_and_metric_metadata_allowlist():
    message = sanitize_message(
        "ana@example.com 123.456.789-00 12.345.678/0001-90 -23.5505,-46.6333"
    )
    assert message == "[email] [cpf] [cnpj] [coordinates]"
    service = ObservabilityService()
    service.record_metric(
        ExecutionMetric("x", "ocr", NOW, metadata={"raw_text": "secret", "size_bytes": 4})
    )
    metadata = service.snapshot().execution_metrics[0].metadata
    assert dict(metadata) == {"size_bytes": 4}


def test_health_check_does_not_call_analysis_or_touch_case(monkeypatch):
    class Detector:
        def rust_core(self, **_):
            return type("S", (), {"available": False})()

        exiftool = tesseract = poppler = rust_core

    monkeypatch.setattr(
        "app.observability.health.SettingsService.load",
        lambda self: type(
            "Settings",
            (),
            {"rust_json_enabled": True, "metadata_enabled": True, "ocr_enabled": True},
        )(),
    )
    checks = HealthCheckService(Detector()).run()
    assert checks and all(item.component_id != "analysis_pipeline" for item in checks)


def test_export_uses_only_local_file_write(monkeypatch, tmp_path):
    called = []
    monkeypatch.setattr("socket.socket.connect", lambda *args, **kwargs: called.append(args))
    export_diagnostic(ObservabilityService().snapshot(), tmp_path / "local.json")
    assert called == []


def test_diagnostics_page_consumes_snapshot():
    from app.pages.diagnostics_page import DiagnosticsPage
    from PySide6.QtWidgets import QApplication

    qt_app = QApplication.instance() or QApplication([])
    assert qt_app is not None

    class Checks:
        def run(self):
            return (health("python", OperationalStatus.OK, True),)

    service = ObservabilityService()
    service.set_components(Checks().run())
    page = DiagnosticsPage(service, Checks())
    page.refresh()
    assert "Saudável" in page.health_badge.text()
    assert page.components.rowCount() == 1
    page.timer.stop()

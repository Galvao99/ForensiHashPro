from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from app.observability import (DIAGNOSTIC_SCHEMA_VERSION, HealthCheckService,
    ObservabilityService, aggregate_system_health, diagnostic_payload, export_diagnostic)
from app.observability.models import (ActiveJob, ComponentHealth, ExecutionMetric,
    ExecutionStatus, OperationalStatus)
from app.observability.sanitization import sanitize_message, safe_ref


NOW = datetime.now(timezone.utc)


def health(identifier, status, required=False):
    return ComponentHealth(identifier, identifier, status, NOW, required)


def test_operational_states_are_disjoint_from_epistemic_states():
    assert {item.value for item in OperationalStatus} == {"OK", "DEGRADED", "UNAVAILABLE", "ERROR"}
    assert not {"MATCH", "MISMATCH", "OBSERVED", "UNKNOWN", "NOT_APPLICABLE"} & {item.value for item in OperationalStatus}


def test_system_health_ok():
    assert aggregate_system_health((health("core", OperationalStatus.OK, True),)) is OperationalStatus.OK


def test_required_degraded_degrades_system():
    assert aggregate_system_health((health("core", OperationalStatus.DEGRADED, True),)) is OperationalStatus.DEGRADED


def test_optional_unavailable_does_not_break_system():
    items = (health("core", OperationalStatus.OK, True), health("ocr", OperationalStatus.UNAVAILABLE))
    assert aggregate_system_health(items) is OperationalStatus.OK


def test_required_unavailable_is_error():
    assert aggregate_system_health((health("core", OperationalStatus.UNAVAILABLE, True),)) is OperationalStatus.ERROR


def test_required_error_is_error():
    assert aggregate_system_health((health("core", OperationalStatus.ERROR, True),)) is OperationalStatus.ERROR


def test_execution_metric_derives_duration():
    metric = ExecutionMetric("x", "hash", NOW, NOW + timedelta(milliseconds=12), status=ExecutionStatus.COMPLETED)
    assert metric.duration_ms == 12


def test_recent_errors_are_bounded_and_sanitized():
    service = ObservabilityService(max_errors=2)
    for index in range(3):
        service.record_error(component_id="x", operation="read", error_code=str(index), error=f"C:\\secret\\person{index}.pdf 1.2.3.4")
    errors = service.snapshot().recent_errors
    assert [item.error_code for item in errors] == ["1", "2"]
    assert all("secret" not in item.message and "1.2.3.4" not in item.message for item in errors)


def test_path_reference_is_stable_and_not_a_path():
    assert safe_ref("file", "C:\\Users\\Ana\\cpf.pdf") == safe_ref("file", "C:\\Users\\Ana\\cpf.pdf")
    assert "Ana" not in safe_ref("file", "C:\\Users\\Ana\\cpf.pdf")
    assert sanitize_message("/home/alice/document.pdf") == "[path]"


def test_case_timing_first_result_cache_and_counts():
    service = ObservabilityService(); service.begin_case("sensitive", [("a", 10), ("b", 20)], 4.5)
    service.update_case(completed=1, partial=0, failed=0, pending=1, running=0, cache_hits=1, cache_misses=0, first_result=True)
    service.update_case(completed=1, partial=0, failed=1, pending=0, running=0, cache_hits=1, cache_misses=1, finished=True)
    case = service.snapshot().case_performance
    assert case and case.ingestion_ms == 4.5 and case.first_result_ms is not None and case.total_analysis_ms is not None
    assert (case.cache_hits, case.cache_misses, case.failed) == (1, 1, 1)


def test_engine_metrics_aggregate_failures_and_duration():
    service = ObservabilityService()
    service.record_metric(ExecutionMetric("1", "ocr", NOW, NOW + timedelta(milliseconds=10), status=ExecutionStatus.COMPLETED))
    service.record_metric(ExecutionMetric("2", "ocr", NOW, NOW + timedelta(milliseconds=30), status=ExecutionStatus.FAILED))
    metric = service.snapshot().engine_metrics[0]
    assert (metric.executions, metric.failures, metric.average_duration_ms, metric.status) == (2, 1, 20, OperationalStatus.ERROR)


def test_jobs_do_not_invent_progress():
    service = ObservabilityService(); job = service.start_job(case_ref=None, file_path="secret.pdf", engine_id="analysis_pipeline", operation="analyze")
    assert service.snapshot().active_jobs[0].progress_percent is None
    service.finish_job(job); assert not service.snapshot().active_jobs


def test_job_accepts_real_progress_only_when_supplied():
    job = ActiveJob("x", ExecutionStatus.RUNNING, NOW, progress_percent=25)
    assert job.progress_percent == 25


def test_export_json_is_versioned_and_contains_no_forensic_payload(tmp_path):
    service = ObservabilityService(); service.begin_case("Caso Maria", [("/secret/name.pdf", 4)], 1)
    destination = export_diagnostic(service.snapshot(), tmp_path / "diagnostic.json")
    payload = json.loads(destination.read_text(encoding="utf-8")); serialized = destination.read_text(encoding="utf-8")
    assert payload["diagnostic_schema_version"] == DIAGNOSTIC_SCHEMA_VERSION
    assert "Caso Maria" not in serialized and "/secret/name.pdf" not in serialized
    assert not ({"evidence", "facts", "findings", "occurrences"} & {key.lower() for key in payload})


def test_error_is_only_operational_and_does_not_create_domain_objects():
    service = ObservabilityService(); service.record_error(component_id="ocr", operation="run", error_code="ocr_failed", error=RuntimeError("failed"))
    payload = diagnostic_payload(service.snapshot())
    text = json.dumps(payload)
    assert "MATCH" not in text and "MISMATCH" not in text and "UNKNOWN" not in text
    assert "finding" not in text.lower() and "evidence" not in text.lower()


def test_thread_safe_collection():
    service = ObservabilityService(max_metrics=500)
    def add(index):
        service.record_metric(ExecutionMetric(str(index), "hash", NOW, NOW, status=ExecutionStatus.COMPLETED))
    with ThreadPoolExecutor(max_workers=8) as pool: list(pool.map(add, range(200)))
    assert service.snapshot().engine_metrics[0].executions == 200


def test_health_check_does_not_call_analysis_or_touch_case(monkeypatch):
    class Detector:
        def rust_core(self, **_): return type("S", (), {"available": False})()
        exiftool = tesseract = poppler = rust_core
    monkeypatch.setattr("app.observability.health.SettingsService.load", lambda self: type("Settings", (), {"rust_json_enabled": True, "metadata_enabled": True, "ocr_enabled": True})())
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
    class Checks:
        def run(self): return (health("python", OperationalStatus.OK, True),)
    service = ObservabilityService(); service.set_components(Checks().run())
    page = DiagnosticsPage(service, Checks()); page.refresh()
    assert "Saudável" in page.health_badge.text()
    assert page.components.rowCount() == 1
    page.timer.stop()

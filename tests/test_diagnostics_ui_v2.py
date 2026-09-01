from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QApplication

from app.observability.models import ComponentHealth, ExecutionMetric, ExecutionStatus, OperationalStatus
from app.observability.service import ObservabilityService
from app.pages.diagnostics_page import DiagnosticsPage
from app.presentation.diagnostics_formatting import format_bytes, format_duration
from app.widgets.diagnostics import EngineTimeChart, OperationalStatusBadge


NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class ChecksSpy:
    def __init__(self, components=()): self.components = tuple(components); self.calls = 0
    def run(self): self.calls += 1; return self.components


def component(identifier: str, status: OperationalStatus, *, required: bool = False):
    return ComponentHealth(identifier, identifier.title(), status, NOW, required, message="Mensagem operacional.")


def page_for(qt_app, components=()):
    service = ObservabilityService(); service.set_components(tuple(components)); checks = ChecksSpy(components)
    page = DiagnosticsPage(service, checks); page.timer.stop(); return page, service, checks


@pytest.mark.parametrize(("status", "text", "kind"), [
    (OperationalStatus.OK, "Saudável", "ok"),
    (OperationalStatus.DEGRADED, "Degradado", "degraded"),
    (OperationalStatus.UNAVAILABLE, "Indisponível", "unavailable"),
    (OperationalStatus.ERROR, "Erro", "error"),
])
def test_operational_status_badge_combines_icon_text_and_color_property(qt_app, status, text, kind):
    badge = OperationalStatusBadge(); badge.set_status(status)
    assert text in badge.text() and len(badge.text().split()[0]) == 1
    assert badge.property("statusKind") == kind


def test_general_status_and_engine_counts(qt_app):
    page, _, _ = page_for(qt_app, (component("core", OperationalStatus.OK, required=True), component("ocr", OperationalStatus.UNAVAILABLE)))
    assert "Saudável" in page.health_badge.text()
    assert page.cards["engines"].value.text() == "1 OK"
    assert "1 indisponíveis" in page.cards["engines"].detail.text()


def test_problematic_engines_are_first_by_default(qt_app):
    page, _, _ = page_for(qt_app, tuple(component(status.value.lower(), status) for status in (OperationalStatus.OK, OperationalStatus.UNAVAILABLE, OperationalStatus.DEGRADED, OperationalStatus.ERROR)))
    assert [page.components.item(row, 1).text().split()[-1] for row in range(4)] == ["Erro", "Degradado", "Indisponível", "Saudável"]


@pytest.mark.parametrize(("value", "expected"), [(0, "0 B"), (1024, "1,0 KB"), (40_402_436, "38,5 MB"), (3 * 1024**3, "3,0 GB")])
def test_byte_formatting(value, expected):
    assert format_bytes(value) == expected


@pytest.mark.parametrize(("value", "expected"), [(313, "313 ms"), (6534, "6,53 s"), (120_000, "2,00 min"), (None, "—")])
def test_duration_formatting(value, expected):
    assert format_duration(value) == expected


def test_engine_chart_uses_real_total_and_empty_state(qt_app):
    service = ObservabilityService(); service.record_metric(ExecutionMetric("1", "ocr", NOW, NOW + timedelta(seconds=2), status=ExecutionStatus.COMPLETED))
    service.record_metric(ExecutionMetric("2", "metadata", NOW, NOW + timedelta(seconds=1), status=ExecutionStatus.COMPLETED))
    chart = EngineTimeChart(); chart.update_metrics(service.snapshot().engine_metrics)
    texts = " ".join(label.text() for row in chart._rows for label in row.findChildren(type(chart.coverage_label)))
    assert "ocr" in texts and "66,7%" in texts and "Cobertura de métricas parcial" in chart.coverage_label.text()
    empty = EngineTimeChart(); empty.update_metrics(()); assert "Nenhuma duração" in empty._rows[0].text()


def test_case_status_distribution_and_human_readable_values(qt_app):
    page, service, _ = page_for(qt_app); service.begin_case("sensitive", [("a", 40_402_436)], 6534)
    service.update_case(completed=1, partial=2, failed=3, pending=4, running=1, cache_hits=5, cache_misses=6, first_result=True, finished=True); page.refresh()
    assert page.case_labels["size"].text() == "38,5 MB" and page.case_labels["ingestion"].text() == "6,53 s"
    assert {key: widgets[2].text() for key, widgets in page.file_distribution._bars.items()} == {"completed": "1", "partial": "2", "failed": "3", "running": "1", "pending": "4"}


def test_jobs_show_executing_without_percent_and_real_percent(qt_app):
    page, service, _ = page_for(qt_app); service.start_job(case_ref="case_x", file_path="secret", engine_id="ocr", operation="run")
    page.refresh(); assert page.jobs.item(0, 5).text() == "Executando"
    from app.observability.models import ActiveJob
    with service._lock:
        job_id = next(iter(service._jobs)); old = service._jobs[job_id]
        service._jobs[job_id] = ActiveJob(old.job_id, old.state, old.started_at, old.case_ref, old.file_ref, old.engine_id, old.operation, 42)
    page.refresh(); assert page.jobs.item(0, 5).text() == "42%"


def test_new_error_appears_and_filters_work(qt_app):
    page, service, _ = page_for(qt_app); assert not page.errors.isVisible()
    service.record_error(component_id="ocr", operation="run", error_code="ocr_failed", error=RuntimeError("C:\\private\\name.pdf")); page.refresh()
    assert page.errors.rowCount() == 1 and "private" not in page.errors.item(0, 5).text()
    page.error_component_filter.setCurrentIndex(page.error_component_filter.findData("ocr")); assert page.errors.rowCount() == 1
    page.status_filter.setCurrentText("ERROR"); assert page.components.rowCount() == 0


def test_engine_filter_and_selection_survive_refresh(qt_app):
    page, _, _ = page_for(qt_app, (component("ocr", OperationalStatus.OK), component("core", OperationalStatus.OK)))
    page.engine_filter.setCurrentIndex(page.engine_filter.findData("ocr")); assert page.components.rowCount() == 1
    page.components.selectRow(0); selected = page._selected_key(page.components); page.refresh()
    assert page._selected_key(page.components) == selected and "component_id: ocr" in page.engine_details.text()


def test_copy_summary_contains_only_sanitized_operational_data(qt_app):
    page, service, _ = page_for(qt_app, (component("core", OperationalStatus.OK, required=True),)); service.begin_case("Caso Maria /home/maria", [("/home/maria/cpf.pdf", 10)], 1); page.refresh()
    text = page.copy_summary()
    assert "Caso Maria" not in text and "/home/maria" not in text
    assert all(term not in text.lower() for term in ("evidence", "finding", "ocr text", "fact"))


def test_refresh_does_not_run_health_or_pipeline(qt_app):
    page, service, checks = page_for(qt_app, (component("core", OperationalStatus.OK),))
    calls = {"snapshot": 0}; original = service.snapshot
    def snapshot(): calls["snapshot"] += 1; return original()
    service.snapshot = snapshot
    page.refresh(); page.refresh()
    assert calls["snapshot"] == 2 and checks.calls == 0
    page.run_diagnostics(); assert checks.calls == 1

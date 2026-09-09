from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from PySide6.QtWidgets import QApplication

from app.observability.models import (
    ComponentHealth,
    ExecutionMetric,
    ExecutionStatus,
    OperationalStatus,
)
from app.observability.service import ObservabilityService
from app.pages.diagnostics_page import DiagnosticsPage
from app.presentation.diagnostics_formatting import format_bytes, format_duration
from app.widgets.diagnostics import EngineTimeChart, OperationalStatusBadge
from app.ui.theme import DARK_THEME, LIGHT_THEME, _phase_one_stylesheet


NOW = datetime.now(timezone.utc)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class ChecksSpy:
    def __init__(self, components=()):
        self.components = tuple(components)
        self.calls = 0

    def run(self):
        self.calls += 1
        return self.components


def component(identifier: str, status: OperationalStatus, *, required: bool = False):
    return ComponentHealth(
        identifier, identifier.title(), status, NOW, required, message="Mensagem operacional."
    )


def page_for(qt_app, components=()):
    service = ObservabilityService()
    service.set_components(tuple(components))
    checks = ChecksSpy(components)
    page = DiagnosticsPage(service, checks)
    page.timer.stop()
    return page, service, checks


@pytest.mark.parametrize(
    ("status", "text", "kind"),
    [
        (OperationalStatus.OK, "Saudável", "ok"),
        (OperationalStatus.DEGRADED, "Degradado", "degraded"),
        (OperationalStatus.UNAVAILABLE, "Indisponível", "unavailable"),
        (OperationalStatus.ERROR, "Erro", "error"),
    ],
)
def test_operational_status_badge_combines_icon_text_and_color_property(qt_app, status, text, kind):
    badge = OperationalStatusBadge()
    badge.set_status(status)
    assert text in badge.text() and len(badge.text().split()[0]) == 1
    assert badge.property("statusKind") == kind


def test_general_status_and_engine_counts(qt_app):
    page, _, _ = page_for(
        qt_app,
        (
            component("core", OperationalStatus.OK, required=True),
            component("ocr", OperationalStatus.UNAVAILABLE),
        ),
    )
    assert "Saudável" in page.health_badge.text()
    assert page.cards["engines"].value.text() == "1 OK"
    assert "1 indisponíveis" in page.cards["engines"].detail.text()


def test_problematic_engines_are_first_by_default(qt_app):
    page, _, _ = page_for(
        qt_app,
        tuple(
            component(status.value.lower(), status)
            for status in (
                OperationalStatus.OK,
                OperationalStatus.UNAVAILABLE,
                OperationalStatus.DEGRADED,
                OperationalStatus.ERROR,
            )
        ),
    )
    assert [page.components.item(row, 1).text().split()[-1] for row in range(4)] == [
        "Erro",
        "Degradado",
        "Indisponível",
        "Saudável",
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0, "0 B"), (1024, "1,0 KB"), (40_402_436, "38,5 MB"), (3 * 1024**3, "3,0 GB")],
)
def test_byte_formatting(value, expected):
    assert format_bytes(value) == expected


@pytest.mark.parametrize(
    ("value", "expected"),
    [(0.3, "<1 ms"), (313, "313 ms"), (6534, "6,5 s"), (120_000, "2m 00s"), (None, "—")],
)
def test_duration_formatting(value, expected):
    assert format_duration(value) == expected


def test_engine_chart_uses_real_total_and_empty_state(qt_app):
    service = ObservabilityService()
    service.record_metric(
        ExecutionMetric(
            "1", "ocr", NOW, NOW + timedelta(seconds=2), status=ExecutionStatus.COMPLETED
        )
    )
    service.record_metric(
        ExecutionMetric(
            "2", "metadata", NOW, NOW + timedelta(seconds=1), status=ExecutionStatus.COMPLETED
        )
    )
    chart = EngineTimeChart()
    chart.update_metrics(service.snapshot().engine_metrics)
    texts = " ".join(
        label.text()
        for row in chart._rows
        for label in row.findChildren(type(chart.coverage_label))
    )
    assert "ocr" in texts and "66,7%" in texts and "Wall acumulado" in chart.coverage_label.text()
    empty = EngineTimeChart()
    empty.update_metrics(())
    assert "Nenhuma duração" in empty._rows[0].text()


def test_case_status_distribution_and_human_readable_values(qt_app):
    page, service, _ = page_for(qt_app)
    service.begin_case("sensitive", [("a", 40_402_436)], 6534)
    service.update_case(
        completed=1,
        partial=2,
        failed=3,
        pending=4,
        running=1,
        cache_hits=5,
        cache_misses=6,
        first_result=True,
        finished=True,
    )
    page.refresh()
    assert (
        page.case_labels["size"].text() == "38,5 MB"
        and page.case_labels["ingestion"].text() == "6,5 s"
    )
    assert {key: widgets[2].text() for key, widgets in page.file_distribution._bars.items()} == {
        "completed": "1",
        "partial": "2",
        "failed": "3",
        "running": "1",
        "pending": "4",
    }


def test_jobs_show_executing_without_percent_and_real_percent(qt_app):
    page, service, _ = page_for(qt_app)
    service.start_job(case_ref="case_x", file_path="secret", engine_id="ocr", operation="run")
    page.refresh()
    assert page.jobs.item(0, 5).text() == "Executando"
    from app.observability.models import ActiveJob

    with service._lock:
        job_id = next(iter(service._jobs))
        old = service._jobs[job_id]
        service._jobs[job_id] = ActiveJob(
            old.job_id,
            old.state,
            old.started_at,
            old.case_ref,
            old.file_ref,
            old.engine_id,
            old.operation,
            42,
        )
    page.refresh()
    assert page.jobs.item(0, 5).text() == "42%"


def test_new_error_appears_and_filters_work(qt_app):
    page, service, _ = page_for(qt_app)
    assert not page.errors.isVisible()
    service.record_error(
        component_id="ocr",
        operation="run",
        error_code="ocr_failed",
        error=RuntimeError("C:\\private\\name.pdf"),
    )
    page.refresh()
    assert page.errors.rowCount() == 1 and "private" not in page.errors.item(0, 5).text()
    page.error_component_filter.setCurrentIndex(page.error_component_filter.findData("ocr"))
    assert page.errors.rowCount() == 1
    page.status_filter.setCurrentText("ERROR")
    assert page.components.rowCount() == 0


def test_engine_filter_and_selection_survive_refresh(qt_app):
    page, _, _ = page_for(
        qt_app, (component("ocr", OperationalStatus.OK), component("core", OperationalStatus.OK))
    )
    page.engine_filter.setCurrentIndex(page.engine_filter.findData("ocr"))
    assert page.components.rowCount() == 1
    page.components.selectRow(0)
    selected = page._selected_key(page.components)
    page.refresh()
    assert (
        page._selected_key(page.components) == selected
        and "component_id: ocr" in page.engine_details.text()
    )


def test_copy_summary_contains_only_sanitized_operational_data(qt_app):
    page, service, _ = page_for(qt_app, (component("core", OperationalStatus.OK, required=True),))
    service.begin_case("Caso Maria /home/maria", [("/home/maria/cpf.pdf", 10)], 1)
    page.refresh()
    text = page.copy_summary()
    assert "Caso Maria" not in text and "/home/maria" not in text
    assert all(term not in text.lower() for term in ("evidence", "finding", "ocr text", "fact"))


def test_refresh_does_not_run_health_or_pipeline(qt_app):
    page, service, checks = page_for(qt_app, (component("core", OperationalStatus.OK),))
    calls = {"snapshot": 0}
    original = service.snapshot

    def snapshot():
        calls["snapshot"] += 1
        return original()

    service.snapshot = snapshot
    page.refresh()
    page.refresh()
    assert calls["snapshot"] == 2 and checks.calls == 0
    page.run_diagnostics()
    assert checks.calls == 1


def test_performance_sections_empty_and_completed_session(qt_app):
    page, service, _ = page_for(qt_app)
    assert [page.tabs.tabText(index) for index in range(page.tabs.count())] == [
        "Visão geral",
        "Performance",
        "Engines",
        "Jobs",
        "Erros",
        "Ambiente",
    ]
    assert page.performance_empty.text() == "Nenhuma sessão de performance disponível."
    service.begin_case("case", [("/secret/a.pdf", 1024)], 2.0, cache_entries=1)
    service.update_case(
        completed=1,
        partial=0,
        failed=0,
        pending=0,
        running=0,
        cache_hits=1,
        cache_misses=0,
        first_result=True,
        finished=True,
    )
    page.refresh()
    assert page.performance_labels["files"].value.text() == "1"
    assert page.performance_labels["cache"].value.text() == "100,0%"
    assert "tamanho lógico" in page.performance_labels["bytes"].detail.text()


def test_cancelled_session_and_artifact_detail(qt_app):
    page, service, _ = page_for(qt_app)
    service.begin_case("case", [("/secret/a.pdf", 100)], 0)
    service.record_metric(
        ExecutionMetric(
            "x",
            "ocr",
            NOW,
            NOW + timedelta(milliseconds=12),
            status=ExecutionStatus.PARTIAL,
            file_ref="file_safe",
            operation="ocr",
            metadata={"size_bytes": 100},
        )
    )
    service.update_case(
        completed=0,
        partial=1,
        failed=0,
        pending=0,
        running=0,
        cache_hits=0,
        cache_misses=1,
        finished=True,
        cancelled=True,
    )
    page.refresh()
    page.artifacts.selectRow(0)
    assert page.performance_labels["total"].detail.text() == "Análise cancelada — métricas parciais"
    assert "file_safe" in page.artifact_details.text() and "ocr" in page.artifact_details.text()


def test_diagnostics_theme_rules_use_light_and_dark_tokens():
    light = _phase_one_stylesheet(LIGHT_THEME)
    dark = _phase_one_stylesheet(DARK_THEME)
    assert LIGHT_THEME.background in light and LIGHT_THEME.text_primary in light
    assert DARK_THEME.background in dark and DARK_THEME.text_primary in dark
    assert "QTabWidget::pane" in light and "QTabWidget::pane" in dark


@pytest.mark.parametrize("width", [700, 900, 1200, 1366])
def test_diagnostics_sections_resize_without_page_level_overflow(qt_app, width):
    page, _, _ = page_for(qt_app)
    page.resize(width, 768)
    page.show()
    qt_app.processEvents()
    assert page.tabs.width() <= page.width()
    assert page.width() == width
    page.close()


@pytest.mark.parametrize("theme", [LIGHT_THEME, DARK_THEME], ids=["light", "dark"])
@pytest.mark.parametrize("width", [700, 900, 1200, 1366])
def test_themed_views_keep_tables_inside_viewport(qt_app, theme, width):
    from app.settings import ApplicationPaths
    from app.ui.theme import load_desktop_stylesheet
    from app.widgets.diagnostics import ResponsiveMetricGrid

    original_style = qt_app.styleSheet()
    qt_app.setStyleSheet(load_desktop_stylesheet(ApplicationPaths.discover(), theme))
    page, service, _ = page_for(
        qt_app,
        (component("very_long_engine_identifier_for_readable_layout", OperationalStatus.OK),),
    )
    try:
        service.begin_case("case", [("a", 9_999_999_999_999)], 0)
        service.record_metric(
            ExecutionMetric(
                "sample",
                "very_long_engine_identifier_for_readable_layout",
                NOW,
                duration_ms=1_234_567,
                status=ExecutionStatus.COMPLETED,
                file_ref="file_123456789012",
            )
        )
        service.record_error(
            component_id="parser",
            operation="parse",
            error_code="parse_failed",
            error=RuntimeError("sensitive"),
        )
        page.refresh()
        page.resize(width, 768)
        page.show()
        for index in range(page.tabs.count()):
            page.tabs.setCurrentIndex(index)
            for _ in range(6):
                qt_app.processEvents()
            scroll = page.tabs.widget(index)
            assert page.width() == width
            assert scroll.horizontalScrollBar().maximum() == 0
            assert scroll.widget().width() <= scroll.viewport().width()
        page.tabs.setCurrentIndex(1)
        qt_app.processEvents()
        assert all(
            grid.columns <= (2 if width == 700 else 4)
            for grid in page.findChildren(ResponsiveMetricGrid)
            if grid.isVisible()
        )
        page.artifacts.selectRow(0)
        assert "file_123456789012" in page.artifact_details.text()
    finally:
        page.close()
        qt_app.setStyleSheet(original_style)


def test_ui_exports_sanitized_session_json(qt_app, tmp_path, monkeypatch):
    import json

    page, service, _ = page_for(qt_app)
    destination = tmp_path / "diagnostic.json"
    service.begin_case("Maria /private/person", [("/private/person.pdf", 4)], 0)
    service.record_error(
        component_id="ocr",
        operation="run",
        error_code="ocr_failed",
        error=RuntimeError("Maria 123.456.789-00"),
    )
    monkeypatch.setattr(
        "app.pages.diagnostics_page.QFileDialog.getSaveFileName",
        lambda *_: (str(destination), "JSON"),
    )
    page.export_json()
    content = destination.read_text(encoding="utf-8")
    assert all(term not in content for term in ("Maria", "private", "123.456.789"))
    assert json.loads(content)["performance_schema_version"] == "1.0.0"


def test_numeric_columns_sort_by_value_and_align_right(qt_app):
    from PySide6.QtCore import Qt
    from app.pages.diagnostics_page import NumericItem

    assert NumericItem("900 ms", 900) < NumericItem("1,1 s", 1100)
    assert NumericItem("—", None) < NumericItem("0 ms", 0)
    assert NumericItem("42", 42).textAlignment() & Qt.AlignmentFlag.AlignRight


def test_available_metrics_update_while_session_is_active(qt_app):
    page, service, _ = page_for(qt_app)
    service.begin_case("case", [("a", 4)], 0)
    service.start_job(
        case_ref=None, file_path="a", engine_id="analysis_pipeline", operation="analyze_file"
    )
    page.refresh()
    assert "em andamento" in page.performance_labels["total"].detail.text()
    assert page.performance_labels["ttfr"].value.text() == "—"
    assert page.performance_labels["peak"].value.text() == "1"
    assert page.jobs.rowCount() == 1


def test_stale_snapshot_is_explicit_and_does_not_break_ui(qt_app, monkeypatch):
    page, service, _ = page_for(qt_app)
    old_snapshot = replace(
        service.snapshot(), generated_at=datetime.now(timezone.utc) - timedelta(seconds=30)
    )
    monkeypatch.setattr(service, "snapshot", lambda: old_snapshot)
    page.refresh()
    assert "obsoleto" in page.snapshot_status.text().lower()

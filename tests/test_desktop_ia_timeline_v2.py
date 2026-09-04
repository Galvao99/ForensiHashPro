from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.models.timeline_event import TimelineEvent
from app.pages.timeline_page import TimelinePage
from app.presentation.timeline import (
    TemporalScale, TimelinePresentation, interval_relation,
)
from app.ui.sidebar import Sidebar
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet
from app.settings import ApplicationPaths
from app.widgets.timeline_v2 import cluster_points, format_temporal


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _event(
    event_id: str, timestamp: str | None, *, event_type: str = "creation",
    source_type: str = "metadata", field_path: str | None = None,
    precision: str = "second", timezone_status: str = "unknown",
    timezone: str | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        event_id=event_id, event_type=event_type, category="metadata",
        title=event_id, description="observação técnica", timestamp=timestamp,
        raw_timestamp=timestamp, timezone=timezone,
        timezone_status=timezone_status, precision=precision,
        source_type=source_type, source_engine="test_engine", evidence_ref="evidence",
        filename="sample.pdf", temporal_status="date_only" if precision in {"day", "month", "year"} else "timestamped",
        field_path=field_path, attributes={"origin": "fixture"},
    )


def test_sidebar_exposes_expected_hierarchy_and_routes(qt_app) -> None:
    sidebar = Sidebar()
    assert tuple(sidebar.group_buttons) == ("case", "file", "tools")
    assert {key for _group, _title, items in sidebar.GROUPS for key, _icon, _label in items} == set(sidebar.navigation_buttons)
    assert "timeline" in sidebar.navigation_buttons
    assert "comparison" in sidebar.navigation_buttons
    assert "correlations" in sidebar.navigation_buttons
    case_items = [key for key, _icon, _label in sidebar.GROUPS[0][2]]
    assert case_items == ["general", "timeline", "correlations", "comparison"]
    assert sidebar.brand_logo.height() == 56
    assert not hasattr(sidebar, "file_list")


def test_group_collapse_is_presentation_only(qt_app) -> None:
    sidebar = Sidebar(group_states={"file": True})
    selected = object()
    analytical_state = {"selected": selected, "calls": 0}
    emitted = []
    sidebar.group_state_changed.connect(lambda group, expanded: emitted.append((group, expanded)))
    sidebar.set_group_expanded("file", False)
    assert emitted == [("file", False)]
    assert analytical_state == {"selected": selected, "calls": 0}


def test_groups_share_top_anchored_flow_and_hide_only_own_children(qt_app) -> None:
    sidebar = Sidebar()
    sidebar.set_case("Caso real", 10, "Analisando")
    sidebar.resize(280, 900)
    sidebar.show()
    qt_app.processEvents()
    layout = sidebar.case_section.layout()
    indices = [layout.indexOf(sidebar.group_buttons[key]) for key in ("case", "file", "tools")]
    assert indices == sorted(indices)
    assert all(sidebar.group_buttons[key].parent() is sidebar.case_section for key in ("case", "file", "tools"))

    file_before = sidebar.group_buttons["file"].y()
    tools_before = sidebar.group_buttons["tools"].y()
    sidebar.set_group_expanded("case", False)
    qt_app.processEvents()
    assert sidebar.group_containers["case"].isHidden()
    assert not sidebar.group_containers["file"].isHidden()
    assert sidebar.group_buttons["file"].y() < file_before

    sidebar.set_group_expanded("file", False)
    qt_app.processEvents()
    assert sidebar.group_containers["file"].isHidden()
    assert not sidebar.group_buttons["tools"].isHidden()
    assert sidebar.group_buttons["tools"].y() < tools_before

    sidebar.set_group_expanded("tools", False)
    assert sidebar.group_containers["tools"].isHidden()
    assert sidebar.case_section.layout().stretch(layout.count() - 1) == 0
    sidebar.close()


def test_current_case_identity_is_centered_and_dynamic(qt_app) -> None:
    sidebar = Sidebar()
    sidebar.set_case("123", 10, "Analisando")
    assert sidebar.case_name_label.text() == "123"
    assert sidebar.case_details_label.text() == "10 arquivo(s) · Analisando"
    assert sidebar.case_name_label.alignment() & Qt.AlignmentFlag.AlignHCenter
    assert sidebar.case_details_label.alignment() & Qt.AlignmentFlag.AlignHCenter


def test_global_scrollbar_uses_theme_tokens_and_transparent_track() -> None:
    light = load_desktop_stylesheet(ApplicationPaths.discover(), LIGHT_THEME)
    dark = load_desktop_stylesheet(ApplicationPaths.discover(), DARK_THEME)
    assert LIGHT_THEME.scrollbar_thumb in light
    assert DARK_THEME.scrollbar_thumb in dark
    assert LIGHT_THEME.scrollbar_thumb != DARK_THEME.scrollbar_thumb
    for stylesheet in (light, dark):
        assert "QScrollBar:vertical" in stylesheet
        assert "QScrollBar:horizontal" in stylesheet
        assert "QScrollBar::add-page:vertical" in stylesheet
        assert "background: transparent; border: 0; width: 9px" in stylesheet


def test_views_share_canonical_objects_and_switch_without_analysis(qt_app) -> None:
    events = (_event("one", "2022-03-01"), _event("ref", "2022-04-01", event_type="text_date"))
    result = SimpleNamespace(timeline_events=list(events))
    page = TimelinePage()
    page.update_analysis(result)
    identity = page.presentation.canonical_events
    page.visual_button.click()
    page.detailed_button.click()
    assert identity is page.presentation.canonical_events
    assert page.presentation.canonical_events == events
    assert result.timeline_events == list(events)


def test_unclassified_text_date_remains_reference_with_provenance() -> None:
    primary = _event("primary", "2022-03-01")
    reference = _event("ocr-ref", "2022-03-02", event_type="text_date", source_type="ocr")
    presentation = TimelinePresentation.from_events((primary, reference))
    assert [point.event_id for point in presentation.primary_points] == ["primary"]
    assert presentation.other_references == (reference,)
    assert presentation.other_references[0].source_engine == "test_engine"
    assert presentation.other_references[0].attributes["origin"] == "fixture"


def test_proportional_scale_uses_real_temporal_distance() -> None:
    events = tuple(
        _event(name, value, precision="day")
        for name, value in (("mar", "2022-03-01"), ("oct", "2022-10-01"), ("sep", "2026-09-01"))
    )
    points = TimelinePresentation.from_events(events).primary_points
    scale = TemporalScale.for_points(points)
    assert scale is not None
    positions = [scale.position(point) for point in points]
    assert positions[0] == 0.0 and positions[2] == 1.0
    assert positions[1] is not None and positions[1] < 0.2


def test_clustering_preserves_timestamps_and_order() -> None:
    events = (_event("a", "2022-03-01T10:00:00"), _event("b", "2022-03-01T10:00:01"), _event("c", "2026-09-01T10:00:00"))
    points = TimelinePresentation.from_events(events).primary_points
    scale = TemporalScale.for_points(points)
    assert scale is not None
    clusters = cluster_points(points, scale, 900)
    assert [point.event_id for cluster in clusters for point in cluster.points] == ["a", "b", "c"]
    assert [event.timestamp for event in events] == ["2022-03-01T10:00:00", "2022-03-01T10:00:01", "2026-09-01T10:00:00"]


def test_certificate_validity_is_interval_and_relation_is_factual() -> None:
    start = _event("not-before", "2022-01-01T00:00:00Z", event_type="certificate_validity", field_path="valid_from", timezone_status="explicit", timezone="UTC")
    end = _event("not-after", "2024-01-01T00:00:00Z", event_type="certificate_validity", field_path="valid_until", timezone_status="explicit", timezone="UTC")
    signing = _event("signing", "2023-01-01T00:00:00Z", event_type="signature", timezone_status="explicit", timezone="UTC")
    presentation = TimelinePresentation.from_events((start, signing, end))
    assert len(presentation.intervals) == 1
    assert {point.event_id for point in presentation.primary_points} == {"signing"}
    assert interval_relation(presentation.primary_points[0], presentation.intervals[0]) == "inside"


def test_incompatible_timezone_domains_are_not_compared() -> None:
    aware = _event("aware", "2023-01-01T00:00:00Z", timezone_status="explicit", timezone="UTC")
    naive_start = _event("start", "2022-01-01T00:00:00", event_type="certificate_validity", field_path="valid_from")
    naive_end = _event("end", "2024-01-01T00:00:00", event_type="certificate_validity", field_path="valid_until")
    presentation = TimelinePresentation.from_events((naive_start, aware, naive_end))
    assert interval_relation(presentation.primary_points[0], presentation.intervals[0]) is None
    assert aware.timezone_status == "explicit" and naive_start.timezone is None


def test_date_only_precision_is_visible_without_time() -> None:
    event = _event("date-only", "2021-03-05", precision="day")
    assert format_temporal(event).startswith("05/03/2021")
    assert ":" not in format_temporal(event).split(" (")[0]


def test_visual_semantics_do_not_depend_on_per_type_colors(qt_app) -> None:
    page = TimelinePage()
    page.update_analysis(SimpleNamespace(timeline_events=[_event("one", "2022-03-01")]))
    page.resize(900, 520)
    page.show()
    page.visual_button.click()
    qt_app.processEvents()
    image = page.grab().toImage()
    assert page.visual.accessibleName() == "Timeline visual proporcional"
    assert page.visual.presentation.primary_points[0].event.title == "one"
    assert not image.isNull()
    page.close()

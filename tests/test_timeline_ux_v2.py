from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel

from app.correlation.case_result import CaseFinding, CaseResult, EpistemicState
from app.correlation.v2 import (
    CaseEvidenceIndex,
    CorrelationCandidate,
    CorrelationProvenance,
    EntityType,
    EvidenceGraphCorrelationEngine,
    source_file_identity,
)
from app.correlation.v2.pipeline import CanonicalCasePipelineResult
from app.correlation.v2.pipeline import DocumentDateMetadataTemporalRule
from app.enum.severity import Severity
from app.models.timeline_event import TimelineEvent
from app.pages.timeline_page import TimelinePage
from app.presentation.timeline import (
    TemporalScale,
    TimelinePresentation,
    category_for_event,
)
from app.services.temporal_parser import TemporalParser
from app.settings import ApplicationPaths
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet
from app.widgets.timeline_v2 import (
    TimelineEventRow,
    cluster_points,
    event_detail_rows,
    format_temporal,
)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def event(
    event_id: str,
    timestamp: str | None,
    *,
    event_type: str = "creation",
    category: str = "metadata",
    source_type: str = "metadata",
    source_engine: str = "metadata_engine",
    field: str | None = "PDF:CreateDate",
    precision: str = "second",
    timezone_status: str = "unknown",
    timezone: str | None = None,
    page: int | None = None,
    offset: int | None = None,
) -> TimelineEvent:
    return TimelineEvent(
        event_id=event_id,
        event_type=event_type,
        category=category,
        title=event_id,
        description="Observação técnica proveniente do dataset canônico.",
        timestamp=timestamp,
        raw_timestamp=timestamp,
        timezone=timezone,
        timezone_status=timezone_status,
        precision=precision,
        source_type=source_type,
        source_engine=source_engine,
        evidence_ref="evidence-a",
        filename="sample.pdf",
        temporal_status=(
            "structural_only" if timestamp is None
            else "date_only" if precision in {"day", "month", "year"}
            else "timestamped"
        ),
        page=page,
        offset=offset,
        field_path=field,
        context="Trecho preservado" if event_type == "contract_date" else None,
        attributes={"metadata_group": "PDF"} if category == "metadata" else {},
    )


def result(tmp_path: Path, name: str, events: tuple[TimelineEvent, ...]):
    return SimpleNamespace(
        timeline_events=list(events),
        file_info=SimpleNamespace(name=name, path=tmp_path / name),
        hashes=SimpleNamespace(sha256="a" * 64),
        evidence_source=None,
    )


def test_visual_and_detailed_receive_the_same_presentation_object(
    qt_app, tmp_path: Path,
) -> None:
    page = TimelinePage()
    analysis = result(tmp_path, "same.pdf", (event("created", "2023-01-01"),))

    page.update_analysis(analysis)

    assert page.detailed._presentation is page.presentation
    assert page.visual.presentation is page.presentation
    assert page.presentation.canonical_events[0] is analysis.timeline_events[0]


def test_switching_segmented_view_does_not_access_analysis_again(
    qt_app, tmp_path: Path,
) -> None:
    class SpyResult:
        file_info = SimpleNamespace(name="spy.pdf", path=tmp_path / "spy.pdf")
        hashes = SimpleNamespace(sha256="b" * 64)
        evidence_source = None

        def __init__(self) -> None:
            self.reads = 0

        @property
        def timeline_events(self):
            self.reads += 1
            return [event("spy", "2023-01-01")]

    analysis = SpyResult()
    page = TimelinePage()
    page.update_analysis(analysis)
    page.visual_button.click()
    page.detailed_button.click()

    assert analysis.reads == 1
    assert page.views.currentWidget() is page.detailed


def test_segmented_control_is_compact_centered_and_not_blue_outlined(qt_app) -> None:
    page = TimelinePage()
    stylesheet = load_desktop_stylesheet(ApplicationPaths.discover(), LIGHT_THEME)

    # A previously installed application stylesheet may raise the Qt-reported
    # maximum by a couple of pixels; the component remains compact either way.
    assert page.detailed_button.maximumHeight() <= 30
    assert page.visual_button.maximumHeight() <= 30
    assert "text-align: center" in page.detailed_button.styleSheet()
    checked_rule = stylesheet.split(
        "QPushButton#TimelineModeButton:checked", 1,
    )[1].split("}", 1)[0]
    assert LIGHT_THEME.accent not in checked_rule
    assert "border-bottom" in checked_rule


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        (event("doc", "2023-01-01", event_type="contract_date", category="contract", source_type="native"), "document"),
        (event("sign", "2023-01-01", event_type="signature", category="signature", source_type="digital_signature"), "signature"),
        (event("meta", "2023-01-01"), "metadata"),
        (event("fs", "2023-01-01", event_type="filesystem_modified", category="filesystem", source_type="filesystem"), "filesystem"),
        (event("pdf", None, event_type="pdf_revision", category="pdf_structure", source_type="pdf_structure", precision="second"), "structural"),
        (event("fh", "2023-01-01", event_type="analysis_started", category="operational", source_type="processing"), "fh"),
    ],
)
def test_category_mapping_is_deterministic_and_presentational(item, expected) -> None:
    assert category_for_event(item).key == expected
    assert category_for_event(item) is category_for_event(item)


def test_category_color_does_not_depend_on_severity() -> None:
    base = event("metadata", "2023-01-01")
    warning = replace(base, severity=Severity.WARNING, color="#ff0000")
    assert category_for_event(base) == category_for_event(warning)


def test_day_precision_uses_neutral_interval_center_for_positioning() -> None:
    day = event("day", "2021-03-05", precision="day")
    point = TimelinePresentation.from_events((day,)).primary_points[0]

    assert point.comparable == datetime(2021, 3, 5)
    assert point.position_value == datetime(2021, 3, 5, 12)
    assert format_temporal(day) == "05/03/2021"


def test_real_distance_and_adaptive_ticks_are_preserved() -> None:
    events = tuple(
        event(name, value, precision="day")
        for name, value in (
            ("jan", "2023-01-01"),
            ("near", "2023-01-02"),
            ("far", "2026-08-01"),
        )
    )
    points = TimelinePresentation.from_events(events).primary_points
    scale = TemporalScale.for_points(points)
    assert scale is not None

    positions = [scale.position(point) for point in points]
    assert positions[1] is not None and positions[1] < 0.01
    assert positions[2] == 1.0
    assert 2 <= len(scale.ticks()) <= 5
    assert all(len(tick.label) <= 8 for tick in scale.ticks())


def test_close_and_same_instant_events_cluster_without_false_order() -> None:
    values = (
        event("same-a", "2023-01-01T10:00:00"),
        event("same-b", "2023-01-01T10:00:00", field="XMP:CreateDate"),
        event("near", "2023-01-01T10:00:01"),
        event("far", "2026-01-01T10:00:00"),
    )
    points = TimelinePresentation.from_events(values).primary_points
    scale = TemporalScale.for_points(points)
    assert scale is not None
    clusters = cluster_points(points, scale, 900)

    assert len(clusters[0].points) == 3
    assert clusters[0].points[0].position_value == clusters[0].points[1].position_value
    assert [point.event_id for cluster in clusters for point in cluster.points] == [
        "same-a", "same-b", "near", "far",
    ]


def test_certificate_is_an_explicit_interval_with_both_end_labels() -> None:
    start = event(
        "not-before", "2022-01-01T00:00:00Z",
        event_type="certificate_validity", category="signature",
        source_type="digital_signature", field="valid_from",
        timezone_status="explicit", timezone="UTC",
    )
    end = event(
        "not-after", "2024-01-01T00:00:00Z",
        event_type="certificate_validity", category="signature",
        source_type="digital_signature", field="valid_until",
        timezone_status="explicit", timezone="UTC",
    )
    presentation = TimelinePresentation.from_events((start, end))

    assert len(presentation.intervals) == 1
    assert presentation.intervals[0].label == "VALIDADE DO CERTIFICADO"
    assert format_temporal(presentation.intervals[0].start.event).startswith("01/01/2022")
    assert format_temporal(presentation.intervals[0].end.event).startswith("01/01/2024")


def test_signing_relation_appears_only_from_canonical_case_result(
    tmp_path: Path,
) -> None:
    events = _signature_events()
    analysis = result(tmp_path, "signed.pdf", events)
    source = source_file_identity(
        display_name="signed.pdf", path=tmp_path / "signed.pdf", sha256="a" * 64,
    )
    snapshot = _signing_snapshot(source, events)
    artifact_id = source.stable_id

    plain = TimelinePresentation.from_events(events, artifact_id=artifact_id)
    enriched = TimelinePresentation.from_events(
        events, canonical_result=snapshot, artifact_id=artifact_id,
    )

    assert plain.related_verifications == ()
    assert enriched.intervals[0].verifications
    relation = enriched.intervals[0].verifications[0]
    assert relation.relation == (
        "SigningTime compreendido no intervalo informado pelo certificado."
    )
    text = relation.statement + (relation.relation or "")
    assert "assinatura válida" not in text.casefold()
    assert analysis.timeline_events == list(events)


def test_document_metadata_relation_is_projected_not_recalculated(
    tmp_path: Path,
) -> None:
    events = (
        event(
            "document", "2021-03-05", event_type="contract_date",
            category="contract", source_type="native",
            source_engine="contract_date_extractor", field=None,
            precision="day", page=1, offset=18,
        ),
        event(
            "creation", "2021-03-10T14:32:18",
            field="PDF:CreationDate",
        ),
    )
    source = source_file_identity(
        display_name="contract.pdf", path=tmp_path / "contract.pdf",
        sha256="a" * 64,
    )
    snapshot = _document_metadata_snapshot(source, events)

    plain = TimelinePresentation.from_events(events, artifact_id=source.stable_id)
    enriched = TimelinePresentation.from_events(
        events, canonical_result=snapshot, artifact_id=source.stable_id,
    )

    assert plain.related_verifications == ()
    assert len(enriched.related_verifications) == 1
    verification = enriched.related_verifications[0]
    assert verification.relation == "Metadado posterior à data documental observada."
    assert "diverg" not in (verification.statement + verification.relation).casefold()
    assert all(
        enriched.display_event(event_id).verifications
        for event_id in ("document", "creation")
    )


def test_document_date_label_is_conservative_and_keeps_provenance() -> None:
    document = event(
        "contract", "2021-03-05", event_type="contract_date",
        category="contract", source_type="native",
        source_engine="contract_date_extractor", field=None,
        precision="day", page=1, offset=42,
    )
    display = TimelinePresentation.from_events((document,)).display_events[0]
    details = dict(event_detail_rows(display))

    assert display.title == "Data documental observada"
    assert display.semantic_role == "document_date"
    assert details["Página"] == "1" and details["Offset"] == "42"
    assert "contrato firmado" not in display.title.casefold()


def test_detailed_view_is_vertical_progressive_and_category_labeled(
    qt_app, tmp_path: Path,
) -> None:
    page = TimelinePage()
    page.update_analysis(result(
        tmp_path, "vertical.pdf", (event("created", "2023-01-01"),),
    ))
    row = next(iter(page.detailed.rows.values()))
    labels = [label.text() for label in row.findChildren(QLabel)]

    assert isinstance(row, TimelineEventRow)
    assert "METADADOS" in labels
    assert row.technical_panel.isHidden()
    assert row.findChild(QLabel, "TimelineV2Marker") is not None


def test_event_click_opens_in_viewport_popover_with_existing_provenance(
    qt_app, tmp_path: Path,
) -> None:
    observed = event(
        "clicked", "2023-01-01T10:30:45", page=3, offset=81,
    )
    page = TimelinePage()
    page.update_analysis(result(tmp_path, "click.pdf", (observed,)))
    page.resize(900, 680)
    page.show()
    page.visual_button.click()
    qt_app.processEvents()
    assert page.visual.clusters
    marker = page.visual.clusters[0]

    QTest.mouseClick(
        page.visual,
        Qt.MouseButton.LeftButton,
        pos=QPoint(round(marker.x), round(marker.y)),
    )
    qt_app.processEvents()
    popover_text = "\n".join(
        label.text() for label in page.visual.popover.findChildren(QLabel)
    )

    assert page.visual.popover.isVisible()
    assert "clicked" in popover_text
    assert "Página: 3" in popover_text
    assert "Offset: 81" in popover_text
    assert page.visual.popover.geometry().right() <= page.visual.width()
    assert page.visual.popover.geometry().bottom() <= page.visual.height()
    assert page.views.currentWidget() is page.visual
    page.close()


def test_cluster_click_lists_real_events_without_creating_cluster_event(
    qt_app, tmp_path: Path,
) -> None:
    observed = tuple(
        event(f"close-{index}", f"2023-01-01T10:00:0{index}")
        for index in range(3)
    ) + (event("far", "2026-01-01T10:00:00"),)
    page = TimelinePage()
    page.update_analysis(result(tmp_path, "cluster.pdf", observed))
    page.resize(900, 680)
    page.show()
    page.visual_button.click()
    qt_app.processEvents()
    cluster = next(item for item in page.visual.clusters if len(item.points) == 3)

    QTest.mouseClick(
        page.visual,
        Qt.MouseButton.LeftButton,
        pos=QPoint(round(cluster.x), round(cluster.y)),
    )
    qt_app.processEvents()

    buttons = page.visual.popover.findChildren(
        type(page.visual_button), "TimelinePopoverEvent",
    )
    assert len(buttons) == 3
    assert len(page.presentation.canonical_events) == 4
    assert {point.event_id for point in cluster.points} == {
        "close-0", "close-1", "close-2",
    }
    page.close()


def test_timezone_unknown_is_explicitly_described_without_conversion() -> None:
    item = event("naive", "2023-01-01T10:30:45")
    display = TimelinePresentation.from_events((item,)).display_events[0]
    details = dict(event_detail_rows(display))

    assert format_temporal(item) == "01/01/2023 · 10:30:45"
    assert details["Timezone"] == "não informado"


def test_narrow_layout_has_no_page_wide_horizontal_scroll(
    qt_app, tmp_path: Path,
) -> None:
    page = TimelinePage()
    page.update_analysis(result(
        tmp_path, "narrow.pdf", (event("narrow", "2023-01-01"),),
    ))
    page.resize(700, 700)
    page.show()
    qt_app.processEvents()

    assert page.width() == 700
    assert page.detailed.scroll.horizontalScrollBar().maximum() == 0
    assert page.detailed.minimumSizeHint().width() <= page.width()
    page.close()


@pytest.mark.parametrize("font_scale", (1.25, 1.5))
def test_narrow_layout_remains_shrinkable_with_larger_font(
    qt_app, tmp_path: Path, font_scale: float,
) -> None:
    original = qt_app.font()
    scaled = QFont(original)
    base_size = original.pointSizeF() if original.pointSizeF() > 0 else 9.0
    scaled.setPointSizeF(base_size * font_scale)
    qt_app.setFont(scaled)
    try:
        page = TimelinePage()
        page.update_analysis(result(
            tmp_path,
            "nome_de_artefato_extenso_para_validacao_responsiva.pdf",
            (event(
                "scaled", "2023-01-01",
                source_engine="provedor_temporal_com_nome_extenso",
            ),),
        ))
        page.resize(700, 760)
        page.show()
        qt_app.processEvents()
        row = next(iter(page.detailed.rows.values()))

        assert page.minimumSizeHint().width() <= 700
        assert row.minimumSizeHint().width() <= page.detailed.scroll.viewport().width()
        assert page.detailed.scroll.horizontalScrollBar().maximum() == 0
        page.close()
    finally:
        qt_app.setFont(original)


def test_selection_is_preserved_across_views_and_cleared_for_new_artifact(
    qt_app, tmp_path: Path,
) -> None:
    page = TimelinePage()
    first = event("first", "2023-01-01")
    page.update_analysis(result(tmp_path, "first.pdf", (first,)))
    page._select_event("first")
    page.visual_button.click()
    page.detailed_button.click()
    assert page.selected_event_id == "first"

    page.update_analysis(result(
        tmp_path, "second.pdf", (event("second", "2024-01-01"),),
    ))
    assert page.selected_event_id is None
    assert page.visual.selected_event_id is None
    assert page.visual.popover.isHidden()


def test_stale_case_snapshot_is_rejected_and_case_change_clears_relations(
    qt_app, tmp_path: Path,
) -> None:
    events = _signature_events()
    analysis = result(tmp_path, "signed.pdf", events)
    source = source_file_identity(
        display_name="signed.pdf", path=tmp_path / "signed.pdf",
        sha256="a" * 64,
    )
    snapshot = _signing_snapshot(source, events)
    page = TimelinePage()
    page.update_analysis(analysis)

    page.update_case_result("case-2", snapshot)
    assert page.presentation.related_verifications == ()

    page.update_case_result("case-1", snapshot)
    assert page.presentation.related_verifications

    page.update_case_result("case-2", None)
    assert page.presentation.related_verifications == ()


def test_large_dataset_keeps_canonical_events_but_limits_widget_creation(
    qt_app, tmp_path: Path,
) -> None:
    events = tuple(
        event(f"event-{index}", f"2023-01-{(index % 28) + 1:02d}T10:00:00")
        for index in range(800)
    )
    page = TimelinePage()
    page.update_analysis(result(tmp_path, "large.pdf", events))

    assert len(page.presentation.canonical_events) == 800
    assert page.detailed.rendered_event_count == page.detailed.INITIAL_RENDER_LIMIT
    assert page.visual.findChildren(TimelineEventRow) == []


@pytest.mark.parametrize("tokens", (LIGHT_THEME, DARK_THEME))
def test_light_dark_expose_semantic_timeline_tokens(tokens) -> None:
    stylesheet = load_desktop_stylesheet(ApplicationPaths.discover(), tokens)
    values = {
        tokens.timeline_document,
        tokens.timeline_signature,
        tokens.timeline_metadata,
        tokens.timeline_filesystem,
        tokens.timeline_structural,
        tokens.timeline_fh,
        tokens.timeline_certificate,
    }

    assert len(values) == 7
    assert all(value in stylesheet for value in values)
    assert "QWidget#VisualTimeline" in stylesheet
    assert "TimelinePopover" in stylesheet


def _signature_events() -> tuple[TimelineEvent, ...]:
    return (
        event(
            "not-before", "2022-01-01T00:00:00Z",
            event_type="certificate_validity", category="signature",
            source_type="digital_signature", field="valid_from",
            timezone_status="explicit", timezone="UTC",
        ),
        event(
            "signing", "2023-01-01T00:00:00Z",
            event_type="signature", category="signature",
            source_type="digital_signature", field="signing_time",
            timezone_status="explicit", timezone="UTC",
        ),
        event(
            "not-after", "2024-01-01T00:00:00Z",
            event_type="certificate_validity", category="signature",
            source_type="digital_signature", field="valid_until",
            timezone_status="explicit", timezone="UTC",
        ),
    )


def _signing_snapshot(source, events) -> CanonicalCasePipelineResult:
    roles = {
        "signing_time": "signer_declared_signing_time",
        "valid_from": "certificate_not_before",
        "valid_until": "certificate_not_after",
    }
    candidates = []
    for item in events:
        parsed = TemporalParser().parse(item.timestamp)
        assert parsed is not None and item.field_path is not None
        candidates.append(CorrelationCandidate(
            EntityType.TIMESTAMP,
            parsed.raw,
            source,
            CorrelationProvenance(
                engine="digital_signature_engine",
                source_type="pdf_embedded_signature",
                field=item.field_path,
                path=item.field_path,
                timestamp_precision=parsed.precision,
                timezone_status=parsed.timezone_status,
            ),
            normalization_value=parsed.normalized,
            semantic_role=roles[item.field_path],
        ))
    graph = EvidenceGraphCorrelationEngine().correlate(candidates)
    index = CaseEvidenceIndex(graph)
    supports = tuple(
        occurrence.occurrence_id
        for role in roles.values()
        for occurrence in index.by_semantic_role(role)
    )
    finding = CaseFinding(
        rule_id="case.signing_time_certificate_validity",
        rule_version="1",
        epistemic_state=EpistemicState.MATCH,
        severity=Severity.INFO,
        title="SigningTime dentro do intervalo do certificado",
        statement=(
            "O SigningTime observado está dentro do intervalo NotBefore/NotAfter "
            "declarado pelo certificado associado."
        ),
        supporting_occurrence_ids=supports,
        metadata={"position": "inside"},
    )
    return CanonicalCasePipelineResult(
        graph, index, CaseResult("case-1", findings=(finding,)),
    )


def _document_metadata_snapshot(source, events) -> CanonicalCasePipelineResult:
    roles = {
        "document": "document_date",
        "creation": "pdf_creation_date",
    }
    candidates = []
    for item in events:
        parsed = TemporalParser().parse(item.timestamp)
        assert parsed is not None
        field = "document_date" if item.event_id == "document" else item.field_path
        candidates.append(CorrelationCandidate(
            EntityType.TIMESTAMP,
            parsed.raw,
            source,
            CorrelationProvenance(
                engine=item.source_engine,
                source_type=item.source_type,
                field=field,
                path=field,
                page=item.page,
                offset_start=item.offset,
                timestamp_precision=parsed.precision,
                timezone_status=parsed.timezone_status,
            ),
            normalization_value=parsed.normalized,
            semantic_role=roles[item.event_id],
        ))
    graph = EvidenceGraphCorrelationEngine().correlate(candidates)
    index = CaseEvidenceIndex(graph)
    findings = DocumentDateMetadataTemporalRule().evaluate(index)
    assert len(findings) == 1
    return CanonicalCasePipelineResult(
        graph, index, CaseResult("case-1", findings=findings),
    )

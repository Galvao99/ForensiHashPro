from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.models.binary_analysis_result import BinaryAnalysisResult
from app.models.binary_finding import BinaryFinding
from app.models.pdf_raw_analysis_result import (
    PdfRawAnalysisResult,
    PdfRawObject,
    PdfStartXref,
)
from app.pages.integrity_page import IntegrityPage
from app.widgets.current_file_badge import CurrentFileBadge
from app.widgets.document_structure_card import DocumentStructureCard
from app.widgets.technical_metric_badge import TechnicalMetricBadge


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def visible_text(widget) -> str:
    return "\n".join(
        label.text()
        for label in widget.findChildren(QLabel)
        if label.isVisibleTo(widget)
    )


def pdf_result(**changes: object) -> PdfRawAnalysisResult:
    values = {
        "version": "1.7",
        "header_offset": 0,
        "objects": [PdfRawObject(1, 0, 9, 40, True)],
        "stream_count": 1,
        "trailer_offsets": [80],
        "startxrefs": [PdfStartXref(100, 80)],
        "eof_offsets": [120, 150],
        "encrypted": True,
        "has_javascript": True,
        "has_acroform": True,
        "findings": [
            BinaryFinding(
                code="pdf_multiple_eof",
                title="Múltiplos marcadores EOF",
                description="Foram observados dois marcadores EOF.",
                offset=150,
            )
        ],
    }
    values.update(changes)
    return PdfRawAnalysisResult(**values)


def badge(
    card: DocumentStructureCard,
    concept_key: str,
) -> TechnicalMetricBadge:
    return next(item for item in card.badges if item.concept_key == concept_key)


def shown_card(
    qt_app,
    result: PdfRawAnalysisResult | None = None,
) -> DocumentStructureCard:
    card = DocumentStructureCard()
    card.update_result(result or pdf_result())
    card.show()
    qt_app.processEvents()
    return card


def test_document_structure_card_creates_summary_badges(qt_app) -> None:
    card = shown_card(qt_app)
    summary_keys = {
        "pdf_version",
        "objects",
        "streams",
        "trailer",
        "startxref",
        "eof",
    }

    assert summary_keys <= {item.concept_key for item in card.badges}
    assert badge(card, "pdf_version").value_label.text() == "1.7"
    assert badge(card, "objects").label_label.text() == "objeto"
    assert badge(card, "eof").value_label.text() == "2"


def test_document_structure_card_creates_present_and_absent_feature_badges(
    qt_app,
) -> None:
    card = shown_card(qt_app)

    assert badge(card, "javascript").value_label.text() == "detectado"
    assert badge(card, "javascript").property("detected") is True
    assert badge(card, "xfa").value_label.text() == "não detectado"
    assert badge(card, "xfa").property("detected") is False
    assert len(card.badges) == 13


def test_badge_click_opens_correct_concept_and_another_replaces_it(
    qt_app,
) -> None:
    card = shown_card(qt_app)
    badge(card, "streams").click()

    assert card.explanation_panel.isVisibleTo(card)
    assert card.explanation_panel.title_label.text() == "Streams"
    assert card.selected_concept_key == "streams"

    badge(card, "xfa").click()

    assert card.explanation_panel.title_label.text() == "XFA"
    assert card.selected_concept_key == "xfa"
    assert not badge(card, "streams").isChecked()


def test_clicking_selected_badge_closes_panel(qt_app) -> None:
    card = shown_card(qt_app)
    selected = badge(card, "eof")
    selected.click()
    selected.click()

    assert not card.explanation_panel.isVisible()
    assert card.selected_concept_key is None
    assert not selected.isChecked()


def test_close_button_hides_panel(qt_app) -> None:
    card = shown_card(qt_app)
    selected = badge(card, "open_action")
    selected.click()
    card.explanation_panel.close_button.click()

    assert not card.explanation_panel.isVisible()
    assert card.selected_concept_key is None
    assert not selected.isChecked()


def test_updating_result_clears_selection_and_previous_badges(qt_app) -> None:
    card = shown_card(qt_app)
    previous = badge(card, "javascript")
    previous.click()
    card.update_result(
        pdf_result(version="2.0", has_javascript=False, has_xfa=True)
    )

    assert card.selected_concept_key is None
    assert not card.explanation_panel.isVisible()
    assert previous not in card.badges
    assert badge(card, "pdf_version").value_label.text() == "2.0"
    assert badge(card, "javascript").value_label.text() == "não detectado"
    assert badge(card, "xfa").value_label.text() == "detectado"


def test_update_none_closes_panel_and_shows_neutral_state(qt_app) -> None:
    card = shown_card(qt_app)
    badge(card, "acroform").click()
    card.update_result(None)
    qt_app.processEvents()

    assert card.badges == ()
    assert card.selected_concept_key is None
    assert not card.explanation_panel.isVisible()
    assert not card.content.isVisible()
    assert "Análise estrutural não disponível" in visible_text(card)


def test_findings_continue_to_be_displayed(qt_app) -> None:
    card = shown_card(qt_app)

    assert "Múltiplos marcadores EOF" in visible_text(card)
    assert "Foram observados dois marcadores EOF." in visible_text(card)


def test_integrity_page_uses_embedded_analysis_and_selected_file(qt_app) -> None:
    raw = pdf_result()
    binary = BinaryAnalysisResult(
        file_size=151,
        header_bytes=b"%PDF-1.7",
        footer_bytes=b"%%EOF",
        pdf_raw_analysis=raw,
    )
    result = SimpleNamespace(
        file_info=SimpleNamespace(
            name="contrato-pericial-com-nome-extenso.pdf",
            path=Path("contrato-pericial-com-nome-extenso.pdf"),
        ),
        integrity=SimpleNamespace(
            hash_verified=True,
            magic_number_verified=True,
            is_structurally_valid=True,
            digital_signature_analysis_status=None,
            encrypted=True,
            javascript_detected=True,
            embedded_files=False,
            incremental_updates=0,
        ),
        binary_analysis=binary,
    )
    page = IntegrityPage()
    page.update_analysis(result)

    assert page.structure_card.content.isVisibleTo(page.structure_card)
    assert badge(page.structure_card, "pdf_version").value_label.text() == "1.7"
    assert page.current_file_badge.file_name == result.file_info.name
    assert page.current_file_badge.toolTip() == result.file_info.name


def test_current_file_badge_elides_and_keeps_full_tooltip(qt_app) -> None:
    badge_widget = CurrentFileBadge()
    full_name = "documento-com-nome-muito-longo-para-o-badge.pdf"
    badge_widget.resize(120, 24)
    badge_widget.set_file_name(full_name)

    assert badge_widget.toolTip() == full_name
    assert badge_widget.text() != full_name
    assert "…" in badge_widget.text()

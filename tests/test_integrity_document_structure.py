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


def pdf_result() -> PdfRawAnalysisResult:
    return PdfRawAnalysisResult(
        version="1.7",
        header_offset=0,
        objects=[PdfRawObject(1, 0, 9, 40, True)],
        stream_count=1,
        trailer_offsets=[80],
        startxrefs=[PdfStartXref(100, 80)],
        eof_offsets=[120, 150],
        encrypted=True,
        has_javascript=True,
        has_acroform=True,
        findings=[
            BinaryFinding(
                code="pdf_multiple_eof",
                title="Múltiplos marcadores EOF",
                description="Foram observados dois marcadores EOF.",
                offset=150,
            )
        ],
    )


def test_document_structure_card_presents_parser_result(qt_app) -> None:
    card = DocumentStructureCard()
    card.update_result(pdf_result())
    card.show()
    qt_app.processEvents()
    text = visible_text(card)

    for expected in (
        "Estrutura do Documento",
        "Versão do PDF:",
        "1.7",
        "Objetos:",
        "Streams:",
        "Trailers:",
        "Startxref:",
        "Marcadores EOF:",
        "JavaScript",
        "Encrypt",
        "AcroForm",
        "0x50",
        "0x64",
        "0x78, 0x96",
        "Múltiplos marcadores EOF",
    ):
        assert expected in text


def test_document_structure_card_has_neutral_unavailable_state(qt_app) -> None:
    card = DocumentStructureCard()
    card.update_result(None)
    card.show()
    qt_app.processEvents()

    assert "Análise estrutural não disponível" in visible_text(card)


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
    assert page.current_file_badge.file_name == result.file_info.name
    assert page.current_file_badge.toolTip() == result.file_info.name


def test_current_file_badge_elides_and_keeps_full_tooltip(qt_app) -> None:
    badge = CurrentFileBadge()
    full_name = "documento-com-nome-muito-longo-para-o-badge.pdf"
    badge.resize(120, 24)
    badge.set_file_name(full_name)

    assert badge.toolTip() == full_name
    assert badge.text() != full_name
    assert "…" in badge.text()

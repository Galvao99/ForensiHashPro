from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QProgressBar,
    QWidget,
)

from app.knowledge.summary_builder import SummaryBuilder
from app.models import (
    AnalysisResult,
    DigitalSignatureResult,
    FileInfo,
    Finding,
    HashResult,
    MagicNumberResult,
    MetadataResult,
    SignatureAnalysisStatus,
)
from app.models.comparison_result import ComparisonResult
from app.models.comparison_section import ComparisonSection
from app.models.integrity_result import IntegrityResult
from app.enum.severity import Severity
from app.pages.comparison_workspace import ComparisonWorkspace
from app.pages.finding_page import FindingPage
from app.ui.main_window import MainWindow
from app.widgets.binary_analyzer.finding_table import FindingsTable
from app.widgets.binary_analyzer.summary_card import (
    SummaryCard as BinarySummaryCard,
)
from app.widgets.analyzed_file_card import AnalyzedFileCard
from app.widgets.finding_item_card import FindingItemCard
from app.widgets.file_investigation_panel import FileInvestigationPanel
from app.widgets.integrity_card import IntegrityCard
from app.widgets.metadata_card import MetadataCard
from app.widgets.summary_card import SummaryCard
from app.widgets.analysis_dashboard import AnalysisDashboard
from app.widgets.flow_layout import FlowLayout


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def analysis_result() -> AnalysisResult:
    return AnalysisResult(
        file_info=FileInfo(
            name="evidence.pdf",
            path=Path("C:/internal/case/evidence.pdf"),
            extension=".pdf",
            size_bytes=100,
            created_at=datetime.now(),
        ),
        hashes=HashResult("a", "b", "c", "d", "e", "f"),
        metadata=MetadataResult(raw={"PDF:Producer": "iText"}),
        findings=[
            Finding(
                severity=Severity.INFO,
                category="Teste",
                title="Estado observado",
                description="Descrição factual",
                evidence_source="Metadados",
                observed_value="Valor",
                recommendation="Revisar evidência",
                score=0.42,
            )
        ],
        magic_numbers=MagicNumberResult(
            detected_type="PDF Document",
            detected_format="PDF",
            signature="25 50 44 46 2D",
            extension_matches=True,
        ),
        digital_signature=DigitalSignatureResult(
            has_signature=False,
            analysis_status=SignatureAnalysisStatus.ABSENT,
        ),
        integrity=IntegrityResult(
            score=12,
            technical_status="Estado factual",
            is_structurally_valid=True,
            hash_verified=True,
            magic_number_verified=True,
            digital_signature_present=False,
            digital_signature_analysis_status=(
                SignatureAnalysisStatus.ABSENT
            ),
            header_valid=True,
            eof_valid=True,
            encrypted=False,
            javascript_detected=False,
            embedded_files=False,
            xref_valid=True,
            trailer_valid=True,
            incremental_updates=0,
        ),
        extracted_text="Texto extraído",
    )


def _visible_text(widget) -> str:
    return "\n".join(
        label.text()
        for label in widget.findChildren(QLabel)
    )


def _assert_no_aggregate_evaluation(widget) -> None:
    text = _visible_text(widget).lower()
    for forbidden in (
        "score geral",
        "score de compatibilidade",
        "confiança/peso técnico",
        "/100",
        "risco baixo",
        "risco médio",
        "risco alto",
        "confiança alta",
        "confiança moderada",
        "confiança baixa",
    ):
        assert forbidden not in text


def test_dashboard_summary_is_factual_and_has_no_internal_path(
    qt_app,
    analysis_result: AnalysisResult,
) -> None:
    summary = SummaryBuilder().build(
        analysis_result,
        correlation_count=3,
    )
    card = SummaryCard()
    card.update_summary(summary)
    text = _visible_text(card)

    assert "evidence.pdf" in text
    assert "Hashes calculados:" in text
    assert "Magic number:" in text
    assert "Vestígios técnicos:" in text
    assert "Correlações:" in text
    assert "3" in text
    assert "Texto extraído:" in text
    assert "C:/internal" not in text
    _assert_no_aggregate_evaluation(card)
    assert card.findChildren(QProgressBar) == []


def test_analyzed_file_card_shows_only_safe_file_origin(
    qt_app,
    analysis_result: AnalysisResult,
) -> None:
    card = AnalyzedFileCard()
    card.update_analysis(analysis_result)

    visible_text = _visible_text(card)
    tooltips = "\n".join(
        widget.toolTip()
        for widget in card.findChildren(QWidget)
        if widget.toolTip()
    )
    rendered_content = f"{visible_text}\n{tooltips}"

    assert card.file_name_label.text() == "evidence.pdf"
    assert card.path_value.text() == "case"
    assert card.path_value.toolTip() == "case"
    assert "C:/internal/case/evidence.pdf" not in rendered_content
    assert "C:\\internal\\case\\evidence.pdf" not in rendered_content


def test_file_cards_share_collision_aware_origin_policy(
    qt_app,
    analysis_result: AnalysisResult,
) -> None:
    peers = [
        Path("C:/case-a/documents/evidence.pdf"),
        Path("D:/case-b/documents/evidence.pdf"),
    ]
    analysis_result.file_info = replace(
        analysis_result.file_info,
        path=peers[0],
    )
    analyzed_card = AnalyzedFileCard()
    investigation_panel = FileInvestigationPanel()

    analyzed_card.update_analysis(
        analysis_result,
        peer_paths=peers,
    )
    investigation_panel.update_analysis(
        analysis_result,
        peer_paths=peers,
    )

    assert analyzed_card.path_value.text() == "case-a/documents"
    assert investigation_panel.path_value.toPlainText() == (
        "case-a/documents"
    )
    rendered = "\n".join(
        (
            _visible_text(analyzed_card),
            analyzed_card.path_value.toolTip(),
            investigation_panel.path_value.toPlainText(),
            investigation_panel.path_value.toolTip(),
        )
    )
    for private_value in ("C:", "D:", "Users", "OneDrive"):
        assert private_value not in rendered


def test_integrity_card_shows_independent_states(
    qt_app,
    analysis_result: AnalysisResult,
) -> None:
    card = IntegrityCard()
    card.update_integrity(analysis_result)
    text = _visible_text(card)

    for expected in (
        "Hash calculado: Sim",
        "Magic number: Compatível",
        "Estrutura PDF: Válida",
        "Assinatura digital: Ausente",
        "JavaScript PDF: Não detectado",
        "Atualizações incrementais: 0",
    ):
        assert expected in text
    _assert_no_aggregate_evaluation(card)
    assert card.findChildren(QProgressBar) == []


def test_comparison_uses_factual_counts_without_percentage(
    qt_app,
) -> None:
    workspace = ComparisonWorkspace(analysis_service=object())
    result = ComparisonResult(
        left_file="left.pdf",
        right_file="right.pdf",
        sections=[
            ComparisonSection("Hash", "success", "Iguais"),
            ComparisonSection("Magic", "warning", "Diferentes"),
            ComparisonSection("Assinatura", "info", "Não aplicável"),
        ],
        technical_summary="Comparação técnica concluída.",
    )
    workspace.update_dashboard(result)
    text = _visible_text(workspace)

    assert "1 item(ns) compatível(is)" in text
    assert "1 divergente(s)" in text
    assert "1 não aplicável(is)" in text
    assert "%" not in text
    _assert_no_aggregate_evaluation(workspace)
    assert workspace.findChildren(QProgressBar) == []


def test_finding_metadata_and_binary_views_hide_confidence(
    qt_app,
    analysis_result: AnalysisResult,
) -> None:
    finding_card = FindingItemCard(analysis_result.findings[0])
    metadata_card = MetadataCard()
    metadata_card.update_metadata(analysis_result.metadata)
    binary_summary = BinarySummaryCard()
    binary_summary.update_result(analysis_result.magic_numbers)
    binary_table = FindingsTable()
    binary_table.update_result(analysis_result.magic_numbers)

    combined_text = "\n".join(
        _visible_text(widget)
        for widget in (
            finding_card,
            metadata_card,
            binary_summary,
            binary_table,
        )
    ).lower()
    assert "descrição factual" in combined_text
    assert "revisar evidência" in combined_text
    assert "confiança" not in combined_text
    assert "%" not in combined_text
    assert binary_table.table.columnCount() == 5


def test_main_window_can_be_constructed(qt_app) -> None:
    window = MainWindow(analysis_service=object())
    assert window.windowTitle() == "ForensiHash Pro"
    window.close()


def test_findings_page_distinguishes_empty_states(qt_app) -> None:
    page = FindingPage()
    page._render()
    assert "Selecione um arquivo analisado" in _visible_text(page)

    page.current_result = object()
    page.findings = []
    page._render()
    assert "Nenhum vestígio técnico identificado" in _visible_text(page)

    page.findings = [object()]
    page.current_filter = page.FILTER_CRITICAL
    page._render()
    assert "Nenhum vestígio corresponde ao filtro" in _visible_text(page)


def test_findings_page_reflows_filters_and_details_panel(qt_app) -> None:
    page = FindingPage()
    assert isinstance(
        page.summary_buttons[page.FILTER_ALL].parentWidget().layout(),
        FlowLayout,
    )

    page.resize(800, 900)
    page.show()
    qt_app.processEvents()
    assert page.body_splitter.orientation() == Qt.Vertical
    assert page.file_panel.minimumWidth() < 350

    page.resize(1280, 900)
    qt_app.processEvents()
    assert page.body_splitter.orientation() == Qt.Horizontal
    assert page.file_panel.minimumWidth() == 350
    page.close()


def test_general_dashboard_stacks_cards_at_compact_width(qt_app) -> None:
    dashboard = AnalysisDashboard()
    dashboard.resize(700, 800)
    dashboard.show()
    qt_app.processEvents()
    compact_position = dashboard.cards_grid.getItemPosition(
        dashboard.cards_grid.indexOf(dashboard.findings_preview_card)
    )
    assert compact_position[:2] == (1, 0)

    dashboard.resize(1100, 800)
    qt_app.processEvents()
    wide_position = dashboard.cards_grid.getItemPosition(
        dashboard.cards_grid.indexOf(dashboard.findings_preview_card)
    )
    assert wide_position[:2] == (0, 1)
    dashboard.close()

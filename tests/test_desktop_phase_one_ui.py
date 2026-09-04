from pathlib import Path
from datetime import datetime
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QListWidgetItem

from app.models import (
    AnalysisResult, DigitalSignatureResult, FileInfo, HashResult,
    MagicNumberResult, MetadataResult, SignatureAnalysisStatus,
)
from app.models.integrity_result import IntegrityResult
from app.ui.sidebar import Sidebar
from app.ui.main_window import MainWindow
from app.settings import ApplicationPaths
from app.ui.theme import (
    DARK_THEME,
    LIGHT_THEME,
    brand_logo_path,
    load_desktop_stylesheet,
)
from app.ui.application_identity import application_icon, application_icon_path
from app.widgets.analysis_dashboard import AnalysisDashboard
from app.widgets.file_list import FileListItemWidget
from app.widgets.status_indicator import StatusIndicator


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def analysis_result() -> AnalysisResult:
    return AnalysisResult(
        file_info=FileInfo("evidence.pdf", Path("evidence.pdf"), ".pdf", 100, datetime.now()),
        hashes=HashResult("md5", "sha1", "sha224", "sha256-value", "sha384", "sha512"),
        metadata=MetadataResult({"PDF:Producer": "ForensiHash test"}),
        findings=[],
        magic_numbers=MagicNumberResult("PDF Document", "25 50 44 46", True, detected_format="PDF", mime_type="application/pdf"),
        digital_signature=DigitalSignatureResult(False, analysis_status=SignatureAnalysisStatus.ABSENT),
        integrity=IntegrityResult(
            score=0, technical_status="Estado factual", is_structurally_valid=True,
            hash_verified=True, magic_number_verified=True, digital_signature_present=False,
            digital_signature_analysis_status=SignatureAnalysisStatus.ABSENT,
            header_valid=True, eof_valid=True, encrypted=False,
            javascript_detected=False, embedded_files=False, xref_valid=True,
            trailer_valid=True, incremental_updates=0,
        ),
    )


def _text(widget) -> str:
    return "\n".join(label.text() for label in widget.findChildren(QLabel))


def test_result_header_tracks_selected_result_and_copies_hash(
    qt_app, analysis_result
) -> None:
    dashboard = AnalysisDashboard()
    dashboard.update_analysis(analysis_result)

    assert dashboard.result_header.file_name.text() == "evidence.pdf"
    assert dashboard.result_header.hash_value.text() == analysis_result.hashes.sha256
    assert dashboard.result_header.status.text() == "CONCLUÍDO"
    dashboard.result_header.copy_button.click()
    assert QApplication.clipboard().text() == analysis_result.hashes.sha256

    visible = _text(dashboard)
    assert visible.count("evidence.pdf") == 1
    assert "Resumo Forense" in visible
    assert "Nenhuma assinatura incorporada reportada." in visible

    replacement = replace(
        analysis_result,
        file_info=replace(analysis_result.file_info, name="second.json"),
        hashes=replace(analysis_result.hashes, sha256="second-sha256"),
    )
    dashboard.update_analysis(replacement)
    assert dashboard.result_header.file_name.text() == "second.json"
    assert dashboard.result_header.hash_value.text() == "second-sha256"


def test_sidebar_keeps_navigation_keys_and_uses_uniform_markers(qt_app) -> None:
    sidebar = Sidebar()
    assert set(sidebar.navigation_buttons) == {
        "general", "hashes", "metadata", "findings", "timeline",
        "magic_number", "digital_signature", "integrity", "ocr", "ip",
        "correlations", "comparison", "deep_file_explorer",
    }
    sidebar.set_active_page("metadata")
    assert sidebar.navigation_buttons["metadata"].isChecked()
    assert "Visão geral" in _text(sidebar)
    assert sidebar.brand_logo.accessibleName() == "ForensiHash"


def test_file_type_markers_cover_common_artifacts(qt_app) -> None:
    expected = {
        "evidence.pdf": "PDF", "photo.jpg": "JPG", "data.json": "JSON",
        "page.html": "HTML", "sheet.xlsx": "XLS", "slides.pptx": "PPT",
    }
    for filename, marker in expected.items():
        widget = FileListItemWidget(Path(filename))
        assert widget.type_label.text() == marker


def test_theme_tokens_and_official_logos_are_available() -> None:
    assert DARK_THEME.background == "#0B0D0F"
    assert DARK_THEME.surface != DARK_THEME.background
    assert LIGHT_THEME.background == "#F5F6F8"
    assert brand_logo_path(DARK_THEME) is not None
    assert brand_logo_path(LIGHT_THEME) is not None
    stylesheet = load_desktop_stylesheet(ApplicationPaths.discover())
    assert "#0B0D0F" in stylesheet
    assert "#0B1120" not in stylesheet
    assert "QFrame#ResultHeader" in stylesheet


def test_official_application_icon_uses_central_resource_resolution(qt_app) -> None:
    paths = ApplicationPaths.discover()
    icon_path = application_icon_path(paths)
    assert icon_path == paths.resource(
        "web/frontend/public/assets/forensihash_icon.png"
    )
    assert icon_path.is_file()
    assert not application_icon(paths).isNull()


def test_status_indicator_supports_shared_states(qt_app) -> None:
    indicator = StatusIndicator()
    for state, label in {
        "completed": "CONCLUÍDO",
        "partial": "PARCIAL",
        "failed": "FALHOU",
        "skipped": "NÃO EXECUTADO",
        "unavailable": "INDISPONÍVEL",
    }.items():
        indicator.set_status(state)
        assert indicator.text() == label
        assert indicator.property("status") == state


def test_general_navigation_avoids_duplicate_shell_context(qt_app) -> None:
    window = MainWindow(analysis_service=object())
    window.show_workspace_page("general")
    assert window.context_label.isHidden()
    window.show_workspace_page("hashes")
    assert not window.context_label.isHidden()
    window.close()


def test_case_overview_precedes_selected_file_summary(qt_app, analysis_result) -> None:
    dashboard = AnalysisDashboard()
    dashboard.update_case(
        {
            "case_name": "04-Objeto da Perícia",
            "is_case": True,
            "total": 1,
            "analyzed": 1,
            "pending": 0,
            "analyzing": 0,
            "failed": 0,
            "current_file": "",
        },
        [analysis_result],
        None,
    )
    dashboard.update_analysis(analysis_result)

    assert dashboard.content_layout.indexOf(dashboard.case_overview) < dashboard.content_layout.indexOf(
        dashboard.result_header
    )
    assert "04-Objeto da Perícia" in _text(dashboard.case_overview)
    assert "1 / 1 arquivos analisados" in _text(dashboard.case_overview)
    assert dashboard.summary_eyebrow.text() == "ARQUIVO SELECIONADO"


def test_sidebar_does_not_render_artifact_browser(qt_app) -> None:
    sidebar = Sidebar()
    assert not hasattr(sidebar, "file_list")
    assert not hasattr(sidebar, "file_search")
    assert sidebar.findChildren(FileListItemWidget) == []


def test_selecting_unavailable_result_never_starts_analysis(qt_app, tmp_path: Path) -> None:
    window = MainWindow(analysis_service=object())
    path = tmp_path / "pending.pdf"
    item = QListWidgetItem()
    item.setData(Qt.ItemDataRole.UserRole, str(path))
    calls = []
    window._start_analysis = lambda **kwargs: calls.append(kwargs)

    window.analyze_selected_file(item)

    assert calls == []
    window.close()

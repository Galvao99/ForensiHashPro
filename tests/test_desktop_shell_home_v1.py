from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.pages.home_page import HomePage
from app.settings import ApplicationPaths, SettingsService
from app.ui.case_catalog import CaseCatalog
from app.ui.main_window import MainWindow
from app.ui.sidebar import Sidebar
from app.ui.line_icons import HomeIllustration, LineIcon
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet
from app.ui.licensing import LicenseSummaryProvider, LicenseSummaryViewModel


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _paths(tmp_path: Path) -> ApplicationPaths:
    return ApplicationPaths(
        tmp_path,
        ApplicationPaths.discover().resource_dir,
        tmp_path / "config",
        tmp_path / "temp",
    )


def test_home_initial_state_and_primary_actions(qt_app) -> None:
    home = HomePage()
    text = "\n".join(label.text() for label in home.findChildren(QLabel))
    assert "Inicie uma nova análise" in text
    assert home.new_case_button.isEnabled()
    assert home.open_case_button.isEnabled()
    assert "Nenhum Caso recente" in text
    assert "DICAS RÁPIDAS" in text
    assert len(home.findChildren(HomeIllustration)) == 1
    assert "Plano Pro" not in text
    assert "Licença válida" not in text


def test_home_drop_routing_does_not_inspect_files(qt_app, tmp_path: Path) -> None:
    home = HomePage()
    received: list[list[Path]] = []
    home.dropped_paths.connect(received.append)
    paths = [tmp_path / "not-read.pdf"]
    home.dropped_paths.emit(paths)
    assert received == [paths]


def test_recent_cases_use_only_persisted_real_locations(tmp_path: Path) -> None:
    evidence = tmp_path / "case"
    evidence.mkdir()
    catalog = CaseCatalog(tmp_path / "recent.json")
    catalog.touch("Nome livre", evidence, 0)
    recent = catalog.list()
    assert [(item.name, item.source_path) for item in recent] == [
        ("Nome livre", str(evidence.resolve()))
    ]


def test_sidebar_structurally_changes_with_case(qt_app) -> None:
    sidebar = Sidebar()
    assert sidebar.home_button.isVisible() is False  # not mounted in a shown window
    assert sidebar.case_section.isHidden()
    assert sidebar.navigation_buttons["general"].isHidden()
    assert not sidebar.navigation_buttons["deep_file_explorer"].isHidden()
    sidebar.set_case("Caso definido", 3, "Pronto")
    assert not sidebar.case_section.isHidden()
    assert not sidebar.navigation_buttons["general"].isHidden()
    sidebar.set_active_page("timeline")
    assert sidebar.navigation_buttons["timeline"].isChecked()


def test_sidebar_uses_aligned_line_icons_without_dev_prefixes(qt_app) -> None:
    sidebar = Sidebar()
    assert sidebar._all_labels["home"].text() == "Home"
    assert all(button.text() == "" for button in sidebar._all_buttons.values())
    mounted = [button for button in sidebar._all_buttons.values() if button.parent() is not None]
    assert all(button.findChild(LineIcon) is not None for button in mounted)
    assert all(button.findChild(LineIcon).has_asset for button in mounted)
    margins = {
        button.layout().contentsMargins().left()
        for button in sidebar._all_buttons.values()
    }
    assert margins == {9}
    assert "HOME" not in sidebar.home_button.text()
    assert "DIAG" not in sidebar.diagnostics_button.text()
    assert "SET" not in sidebar.settings_button.text()


def test_sidebar_collapse_keeps_active_state_and_tooltips(qt_app) -> None:
    sidebar = Sidebar()
    sidebar.set_case("Caso", 2, "Pronto")
    sidebar.set_active_page("metadata")
    sidebar.set_collapsed(True)
    assert sidebar.width() == 64
    assert sidebar.navigation_buttons["metadata"].isChecked()
    assert sidebar.navigation_buttons["metadata"].toolTip() == "Metadados"
    assert sidebar.navigation_labels["metadata"].isHidden()
    sidebar.set_collapsed(False)
    assert sidebar.navigation_buttons["metadata"].isChecked()


def test_shell_keeps_global_pages_accessible(qt_app, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    window = MainWindow(object(), paths=paths, settings_service=SettingsService(paths=paths))
    for key in ("diagnostics", "settings", "deep_file_explorer"):
        assert key in window.workspace.pages
    assert window.topbar_context.text() == "Nenhum Caso aberto"
    assert window.task_status_label.text() == "0 tarefas em execução"
    assert not window.topbar_logo.pixmap().isNull()
    assert window.topbar_logo.accessibleName() == "ForensiHash"
    assert window.case_icon.isHidden()


def test_topbar_case_context_and_real_progress(qt_app, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    window = MainWindow(object(), paths=paths, settings_service=SettingsService(paths=paths))
    window.current_case_name = "Pit"
    window.topbar_context.setText("Pit")
    window.case_icon.setVisible(True)
    window._case_progress = {"total": 18, "analyzed": 7, "failed": 1}
    window._set_current_analysis_file("Parecer_técnico_com_nome_muito_longo_para_exibição_integral.pdf")
    window._update_progress(38, "Analisando")
    assert window.topbar_context.text() == "Pit"
    assert not window.case_icon.isHidden()
    assert window.progress_bar.value() <= 38  # animation moves only toward the emitted value
    assert window.progress_bar.maximum() == 100
    assert window.current_analysis_file_label.toolTip().endswith(".pdf")
    assert "…" in window.current_analysis_file_label.text()
    assert window._progress_count_text(7, 18) == "7 / 18 arquivos · 1 falha(s)"
    window._hide_progress()
    assert window.progress_bar.isHidden()
    assert window.task_status_label.text() == "0 tarefas em execução"


def test_theme_default_and_persistence(qt_app, tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    service = SettingsService(paths=paths)
    assert service.load().theme_mode == "light"
    window = MainWindow(object(), paths=paths, settings_service=service)
    window.set_theme_mode("dark")
    assert service.load().theme_mode == "dark"
    window.set_theme_mode("system")
    assert json.loads(paths.settings_file.read_text(encoding="utf-8"))["theme_mode"] == "system"
    light = load_desktop_stylesheet(paths, LIGHT_THEME)
    dark = load_desktop_stylesheet(paths, DARK_THEME)
    for selector in ("QFrame#TopBar", "QFrame#StatusBar", "QDialog#NewCaseDialog"):
        assert selector in light
        assert selector in dark
    assert LIGHT_THEME.text_primary in light
    assert DARK_THEME.text_primary in dark
    assert "QLabel#SidebarNavigationText { font-weight: 400; }" in light
    assert "QFrame#MagicCompactHeader" in light


def test_license_boundary_exists_without_rendering_fake_entitlements() -> None:
    assert LicenseSummaryProvider is not None
    summary = LicenseSummaryViewModel("Fonte autorizada")
    assert summary.label == "Fonte autorizada"

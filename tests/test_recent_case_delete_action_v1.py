from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QPushButton

from app.pages.home_page import HomePage
from app.services.case_deletion_service import CaseDeletionService
from app.settings import ApplicationPaths, SettingsService
from app.ui.case_catalog import CaseCatalog, RecentCase
from app.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _recent(name: str, source: Path, count: int = 1) -> RecentCase:
    case_id = str(source.resolve())
    return RecentCase(name, case_id, count, "2026-09-05T10:32:00+00:00", case_id)


def _paths(tmp_path: Path) -> ApplicationPaths:
    return ApplicationPaths(
        tmp_path,
        ApplicationPaths.discover().resource_dir,
        tmp_path / "config",
        tmp_path / "temp",
    )


def test_recent_card_has_accessible_delete_action_and_separate_clicks(qt_app, tmp_path: Path) -> None:
    first_path = tmp_path / "first"
    second_path = tmp_path / "second"
    first_path.mkdir()
    second_path.mkdir()
    first = _recent("Mesmo nome", first_path)
    second = _recent("Mesmo nome", second_path)
    home = HomePage()
    opened: list[str] = []
    deleted: list[str] = []
    home.recent_case_requested.connect(lambda case: opened.append(case.case_id))
    home.recent_case_delete_requested.connect(lambda case: deleted.append(case.case_id))
    home.set_recent_cases([first, second])

    open_buttons = home.findChildren(QPushButton, "HomeRecentCase")
    delete_buttons = home.findChildren(QPushButton, "HomeRecentCaseDelete")
    assert len(open_buttons) == len(delete_buttons) == 2
    assert all(button.text() == "×" for button in delete_buttons)
    assert all(button.toolTip() == "Excluir caso" for button in delete_buttons)
    assert all(button.accessibleName() == "Excluir caso" for button in delete_buttons)
    assert all(button.width() == button.height() == 28 for button in delete_buttons)

    open_buttons[0].click()
    assert opened == [first.case_id]
    delete_buttons[1].click()
    assert deleted == [second.case_id]
    assert opened == [first.case_id]


def test_delete_service_is_case_id_scoped_and_preserves_original_files(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    first_dir.mkdir()
    second_dir.mkdir()
    original = first_dir / "evidence.pdf"
    other = second_dir / "evidence.pdf"
    original.write_bytes(b"original")
    other.write_bytes(b"other")
    catalog = CaseCatalog(tmp_path / "recent.json")
    first = catalog.touch("Mesmo nome", first_dir, 1)
    second = catalog.touch("Mesmo nome", second_dir, 1)

    result = CaseDeletionService(catalog).delete_case(first.case_id)

    assert result.success
    assert result.removed_recent_entry
    assert [case.case_id for case in catalog.list()] == [second.case_id]
    assert original.exists()
    assert other.exists()


def test_delete_missing_case_is_idempotent(tmp_path: Path) -> None:
    catalog = CaseCatalog(tmp_path / "recent.json")
    result = CaseDeletionService(catalog).delete_case("missing-case")
    assert result.success
    assert not result.removed_recent_entry


def test_catalog_delete_failure_keeps_original_catalog(tmp_path: Path, monkeypatch) -> None:
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    catalog = CaseCatalog(tmp_path / "recent.json")
    case = catalog.touch("Caso", case_dir, 1)
    before = catalog.path.read_bytes()

    def fail_replace(self: Path, target: Path) -> Path:
        raise OSError("disk failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    result = CaseDeletionService(catalog).delete_case(case.case_id)
    assert not result.success
    assert catalog.path.read_bytes() == before


def test_legacy_catalog_entry_gets_source_based_case_id(tmp_path: Path) -> None:
    case_dir = tmp_path / "legacy"
    case_dir.mkdir()
    path = tmp_path / "recent.json"
    path.write_text(json.dumps([{
        "name": "Legado", "source_path": str(case_dir.resolve()),
        "file_count": 2, "last_opened": "2026-09-05T10:32:00+00:00",
    }]), encoding="utf-8")
    case = CaseCatalog(path).list()[0]
    assert case.case_id == str(case_dir.resolve())


def test_main_window_cancel_does_not_change_catalog(qt_app, tmp_path: Path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    window = MainWindow(object(), paths=paths, settings_service=SettingsService(paths=paths))
    recent = window.case_catalog.touch("Caso", case_dir, 0)
    window.workspace.home_page.set_recent_cases(window.case_catalog.list())
    monkeypatch.setattr(window, "_confirm_recent_case_deletion", lambda _case: False)
    window.delete_recent_case(recent)
    assert [case.case_id for case in window.case_catalog.list()] == [recent.case_id]


def test_confirm_delete_removes_card_and_clears_open_case(qt_app, tmp_path: Path, monkeypatch) -> None:
    paths = _paths(tmp_path)
    case_dir = tmp_path / "case"
    case_dir.mkdir()
    evidence = case_dir / "original.txt"
    evidence.write_text("evidence", encoding="utf-8")
    window = MainWindow(object(), paths=paths, settings_service=SettingsService(paths=paths))
    recent = window.case_catalog.touch("Caso", case_dir, 1)
    window.current_case_id = recent.case_id
    window.current_case_name = recent.name
    window.current_folder_path = case_dir
    window._case_result_cache[recent.case_id] = {"cached": object()}
    window.workspace.home_page.set_case_open(True)
    window.sidebar.set_case(recent.name, 1, "Pronto")
    monkeypatch.setattr(window, "_confirm_recent_case_deletion", lambda _case: True)

    window.delete_recent_case(recent)

    assert window.case_catalog.list() == []
    assert window.workspace.home_page.findChildren(QPushButton, "HomeRecentCase") == []
    assert recent.case_id not in window._case_result_cache
    assert window.current_case_id is None
    assert window.current_case_name is None
    assert window.current_folder_path is None
    assert window.current_page_key == "home"
    assert evidence.exists()

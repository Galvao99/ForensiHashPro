from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.settings import ApplicationPaths, SettingsService
from app.ui.main_window import MainWindow
from app.widgets.file_strip import FileStrip, FileStripDelegate, FileStripModel


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _paths(tmp_path: Path) -> ApplicationPaths:
    discovered = ApplicationPaths.discover()
    return ApplicationPaths(tmp_path, discovered.resource_dir, tmp_path / "config", tmp_path / "temp")


@pytest.mark.parametrize("count", [1, 5, 20, 100])
def test_file_strip_models_known_paths_without_reading_files(qt_app, tmp_path: Path, count: int) -> None:
    strip = FileStrip(_paths(tmp_path))
    paths = [tmp_path / f"artifact-{index:03}.pdf" for index in range(count)]
    strip.set_files(paths)
    assert strip.model.rowCount() == count
    assert strip.model.index(count - 1).data(FileStripModel.PathRole) == str(paths[-1])


def test_long_name_is_bounded_and_full_name_is_tooltip(qt_app, tmp_path: Path) -> None:
    strip = FileStrip(_paths(tmp_path))
    path = tmp_path / ("parecer-tecnico-" + "muito-longo-" * 12 + ".pdf")
    strip.set_files([path])
    index = strip.model.index(0)
    assert strip.view.itemDelegate().sizeHint(None, index).width() == FileStripDelegate.WIDTH
    assert index.data(Qt.ItemDataRole.ToolTipRole) == path.name


def test_horizontal_scroll_and_controls_support_many_files(qt_app, tmp_path: Path) -> None:
    strip = FileStrip(_paths(tmp_path))
    strip.resize(500, 55)
    strip.set_files([tmp_path / f"file-{index}.pdf" for index in range(100)])
    strip.show()
    qt_app.processEvents()
    bar = strip.view.horizontalScrollBar()
    assert bar.maximum() > 0
    before = bar.value()
    strip.next_button.click()
    assert bar.value() > before


def test_selection_signal_and_status_are_model_backed(qt_app, tmp_path: Path) -> None:
    strip = FileStrip(_paths(tmp_path))
    paths = [tmp_path / "a.pdf", tmp_path / "b.json"]
    strip.set_files(paths)
    selected: list[Path] = []
    strip.selection_requested.connect(selected.append)
    index = strip.model.index(1)
    strip.view.clicked.emit(index)
    strip.set_selected_path(paths[1])
    strip.set_status(paths[1], "analyzing")
    assert selected == [paths[1]]
    assert strip.selected_path() == paths[1]
    assert index.data(FileStripModel.StatusRole) == "analyzing"


def test_strip_routes_through_canonical_selection(qt_app, tmp_path: Path) -> None:
    paths_config = _paths(tmp_path)
    window = MainWindow(object(), paths=paths_config, settings_service=SettingsService(paths=paths_config))
    paths = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    window.file_strip.set_files(paths)
    window._case_file_states = {str(path.resolve()): "pending" for path in paths}
    window.select_file_from_strip(paths[1])
    assert window.current_selection is not None
    assert window.current_selection.file_path == paths[1]
    assert window.file_strip.selected_path() == paths[1]
    assert not hasattr(window.sidebar, "file_list")


def test_navigation_and_worker_update_do_not_steal_strip_selection(qt_app, tmp_path: Path) -> None:
    paths_config = _paths(tmp_path)
    window = MainWindow(object(), paths=paths_config, settings_service=SettingsService(paths=paths_config))
    paths = [tmp_path / "a.pdf", tmp_path / "b.pdf"]
    window.file_strip.set_files(paths)
    window._case_file_states = {str(path.resolve()): "pending" for path in paths}
    window.select_file_from_strip(paths[1])
    window.show_home_page()
    window._on_file_state_changed(str(paths[0]), "analyzed")
    assert window.file_strip.selected_path() == paths[1]
    assert window.current_selection is not None
    assert window.current_selection.file_path == paths[1]

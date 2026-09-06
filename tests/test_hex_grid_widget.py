from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication

from app.widgets.binary_inspector.hex_grid import HexGridWidget


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def grid(qt_app, size: int = 256) -> HexGridWidget:
    widget = HexGridWidget(); widget.resize(900, 420)

    def provide(offset: int, length: int, request_id: int) -> None:
        widget.accept_window(offset, bytes((offset + index) % 256 for index in range(length)), request_id)

    widget.window_requested.connect(provide)
    widget.set_file(size); widget.show(); qt_app.processEvents()
    return widget


def test_grid_uses_sixteen_bytes_per_line_and_real_offsets(qt_app) -> None:
    widget = grid(qt_app, 64)
    assert widget.BYTES_PER_LINE == 16
    assert widget.offset_at(widget.cell_rect(0).center()) == 0
    assert widget.offset_at(widget.cell_rect(15).center()) == 15
    assert widget.offset_at(widget.cell_rect(16).center()) == 16


def test_partial_final_line_never_invents_bytes(qt_app) -> None:
    widget = grid(qt_app, 18)
    assert widget.byte_at(17) == 17
    assert widget.byte_at(18) is None
    assert widget.go_to_offset(17) and not widget.go_to_offset(18)


@pytest.mark.parametrize("size", [0, 1])
def test_empty_and_single_byte_files(qt_app, size: int) -> None:
    widget = grid(qt_app, size)
    assert widget.file_size == size
    assert widget.go_to_offset(0) is (size == 1)
    assert widget.selection_length == size


def test_click_and_shift_click_create_visual_selection(qt_app) -> None:
    widget = grid(qt_app)
    QTest.mouseClick(widget.viewport(), Qt.LeftButton, pos=widget.cell_rect(3).center())
    QTest.mouseClick(widget.viewport(), Qt.LeftButton, Qt.ShiftModifier, pos=widget.cell_rect(12).center())
    assert (widget.current_offset, widget.selection_start, widget.selection_end, widget.selection_length) == (12, 3, 12, 10)


def test_drag_selects_a_byte_range(qt_app) -> None:
    widget = grid(qt_app)
    start, end = widget.cell_rect(2).center(), widget.cell_rect(20).center()
    QTest.mousePress(widget.viewport(), Qt.LeftButton, pos=start)
    QTest.mouseMove(widget.viewport(), end)
    QTest.mouseRelease(widget.viewport(), Qt.LeftButton, pos=end)
    assert widget.selection_start == 2 and widget.selection_end == 20


def test_hex_and_ascii_zones_resolve_the_same_byte(qt_app) -> None:
    widget = grid(qt_app)
    for offset in (0, 7, 15, 31):
        assert widget.offset_at(widget.cell_rect(offset).center()) == offset
        assert widget.offset_at(widget.cell_rect(offset, ascii_zone=True).center()) == offset


def test_keyboard_byte_line_and_page_navigation(qt_app) -> None:
    widget = grid(qt_app, 4096); widget.go_to_offset(100); widget.setFocus()
    QTest.keyClick(widget, Qt.Key_Right); assert widget.current_offset == 101
    QTest.keyClick(widget, Qt.Key_Left); assert widget.current_offset == 100
    QTest.keyClick(widget, Qt.Key_Down); assert widget.current_offset == 116
    QTest.keyClick(widget, Qt.Key_Up); assert widget.current_offset == 100
    rows = widget.visible_row_capacity
    QTest.keyClick(widget, Qt.Key_PageDown); assert widget.current_offset == 100 + rows * 16
    QTest.keyClick(widget, Qt.Key_PageUp); assert widget.current_offset == 100


def test_home_end_and_controlled_file_navigation(qt_app) -> None:
    widget = grid(qt_app, 1000); widget.go_to_offset(37); widget.setFocus()
    QTest.keyClick(widget, Qt.Key_Home); assert widget.current_offset == 32
    QTest.keyClick(widget, Qt.Key_End); assert widget.current_offset == 47
    QTest.keyClick(widget, Qt.Key_Home, Qt.ControlModifier); assert widget.current_offset == 0
    QTest.keyClick(widget, Qt.Key_End, Qt.ControlModifier); assert widget.current_offset == 999


def test_shift_keyboard_extends_selection(qt_app) -> None:
    widget = grid(qt_app); widget.go_to_offset(20); widget.setFocus()
    QTest.keyClick(widget, Qt.Key_Right, Qt.ShiftModifier)
    QTest.keyClick(widget, Qt.Key_Down, Qt.ShiftModifier)
    assert widget.selection_start == 20 and widget.selection_end == 37


def test_scroll_is_proportional_and_requests_only_a_window(qt_app) -> None:
    widget = HexGridWidget(); widget.resize(900, 420)
    requests = QSignalSpy(widget.window_requested); widget.set_file(1024 * 1024 * 1024)
    initial_count = requests.count()
    widget.verticalScrollBar().setValue(widget.verticalScrollBar().maximum() // 2)
    qt_app.processEvents()
    assert widget._first_line > 20_000_000
    assert requests.count() <= initial_count + 2
    assert widget.visible_row_capacity < 100


def test_cache_is_lru_bounded(qt_app) -> None:
    widget = HexGridWidget(); widget.set_file(20 * widget.WINDOW_BYTES)
    for page in range(widget.CACHE_WINDOWS + 3):
        offset = page * widget.WINDOW_BYTES
        widget.accept_window(offset, b"x" * 16)
    assert widget.cached_window_count == widget.CACHE_WINDOWS
    assert widget.byte_at(0) is None


def test_copy_hex_and_ascii_are_bounded_to_selection(qt_app) -> None:
    widget = grid(qt_app, 64); widget.set_selection(48, 51)
    widget.copy_hex(); qt_app.processEvents()
    assert QApplication.clipboard().text() == "30 31 32 33"
    widget.copy_ascii(); qt_app.processEvents()
    assert QApplication.clipboard().text() == "0123"


def test_context_menu_contains_only_real_actions(qt_app) -> None:
    widget = grid(qt_app); assert widget.create_context_menu().isEmpty()
    widget.go_to_offset(10)
    actions = [action.text() for action in widget.create_context_menu().actions() if not action.isSeparator()]
    assert actions == ["Copy Hex", "Copy ASCII", "Copy Offset", "Set Start Here", "Set End Here",
                       "Detect Type", "Calculate SHA-256", "Extract Selection"]


def test_selection_and_cursor_signals_are_stable(qt_app) -> None:
    widget = grid(qt_app); selections = QSignalSpy(widget.selection_changed); cursors = QSignalSpy(widget.cursor_changed)
    widget.set_selection(4, 9)
    assert list(selections.at(selections.count() - 1)) == [4, 9]
    assert list(cursors.at(cursors.count() - 1)) == [9, 9]


def test_metric_derived_zones_and_all_cells_never_overlap(qt_app) -> None:
    widget = grid(qt_app, 4096); geometry = widget.grid_geometry()
    assert geometry.offset_rect.right() < geometry.hex_rect.left()
    assert geometry.hex_rect.right() < geometry.ascii_rect.left()
    assert len(geometry.hex_cells) == len(geometry.ascii_cells) == 16
    assert geometry.hex_cells[0].left() > geometry.offset_rect.right()
    assert geometry.hex_cells[-1].right() <= geometry.hex_rect.right()
    assert geometry.hex_cells[-1].right() < geometry.ascii_cells[0].left()
    assert geometry.ascii_cells[-1].right() <= geometry.ascii_rect.right()


def test_header_body_and_hit_testing_share_cell_positions(qt_app) -> None:
    widget = grid(qt_app, 64); geometry = widget.grid_geometry()
    for index in (0, 15):
        body_hex = widget.cell_rect(index)
        body_ascii = widget.cell_rect(index, ascii_zone=True)
        assert body_hex.left() == geometry.hex_cells[index].left()
        assert body_ascii.left() == geometry.ascii_cells[index].left()
        assert widget.offset_at(body_hex.center()) == index
        assert widget.offset_at(body_ascii.center()) == index
    body_y = widget.HEADER_HEIGHT + widget._row_height // 2
    assert widget.offset_at(QPoint(geometry.offset_rect.center().x(), body_y)) is None
    gap_x = (geometry.hex_rect.right() + geometry.ascii_rect.left()) // 2
    assert widget.offset_at(QPoint(gap_x, body_y)) is None


def test_zone_titles_are_limited_to_fixed_header_height(qt_app) -> None:
    widget = grid(qt_app, 4096); geometry = widget.grid_geometry()
    for zone in (geometry.offset_rect, geometry.ascii_rect):
        header = widget._header_rect(zone)
        assert header.getRect() == (zone.left(), 0, zone.width(), widget.HEADER_HEIGHT)
        assert header.bottom() < widget.cell_rect(0).bottom()


def test_small_viewport_scrolls_horizontally_instead_of_overlapping(qt_app) -> None:
    widget = grid(qt_app, 256); widget.resize(420, 300); qt_app.processEvents()
    geometry = widget.grid_geometry()
    assert widget.horizontalScrollBar().maximum() > 0
    assert geometry.offset_rect.right() < geometry.hex_rect.left()
    assert geometry.hex_rect.right() < geometry.ascii_rect.left()


@pytest.mark.parametrize("point_size", [9, 12, 15])
def test_larger_font_metrics_preserve_geometry(qt_app, point_size: int) -> None:
    widget = grid(qt_app, 256); font = QFont(widget._font); font.setPointSize(point_size)
    widget.set_grid_font(font); geometry = widget.grid_geometry()
    metrics = widget._metrics
    assert geometry.hex_cells[0].width() >= metrics.horizontalAdvance("FF")
    assert geometry.ascii_cells[0].width() >= metrics.horizontalAdvance("W")
    assert geometry.offset_rect.right() < geometry.hex_rect.left() < geometry.ascii_rect.left()

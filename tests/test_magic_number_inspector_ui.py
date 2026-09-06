from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QScrollArea

from app.engines.magic_number_engine import MagicNumberEngine
from app.pages.magic_number_page import MagicNumberPage
from app.services.byte_range_extraction_service import ByteRangeExtractionService
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet
from app.settings import ApplicationPaths


@pytest.fixture(scope="module")
def qt_app(): return QApplication.instance() or QApplication([])


def result(path: Path, *, name: str | None = None):
    magic = MagicNumberEngine().analyze(path)
    return SimpleNamespace(
        file_info=SimpleNamespace(path=path, name=name or path.name, size_bytes=path.stat().st_size),
        hashes=SimpleNamespace(sha256="source-sha256"), magic_numbers=magic,
    )


def page() -> MagicNumberPage:
    value = MagicNumberPage(ByteRangeExtractionService(max_read_bytes=2 * 1024 * 1024))
    value._submit = lambda operation, success, failure: _run(operation, success, failure)
    return value


def _run(operation, success, failure):
    try: success(operation())
    except Exception as error: failure(str(getattr(error, "category", "unavailable")), str(error))


@pytest.mark.parametrize("name,data,format_name", [("evidence.pdf", b"%PDF-1.7\n%%EOF", "PDF"),
                                                     ("photo.jpg", b"\xff\xd8\xff\xe0\0\x02\xff\xd9", "JPEG"),
                                                     ("random.bin", b"unrecognized", "UNKNOWN")])
def test_header_displays_recognized_and_unknown_formats(qt_app, tmp_path: Path, name: str,
                                                        data: bytes, format_name: str) -> None:
    source = tmp_path / name; source.write_bytes(data); widget = page(); widget.update_analysis(result(source))
    assert widget._result.magic_numbers.detected_format == format_name
    assert widget.signature_value.text() == widget._result.magic_numbers.signature
    assert widget.mime.text() == widget._result.magic_numbers.mime_type


def test_extension_divergence_is_a_neutral_fact(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "document.bin"; source.write_bytes(b"%PDF-1.7\n%%EOF")
    widget = page(); widget.update_analysis(result(source))
    assert "não corresponde" in widget.match_value.text()


def test_actions_follow_valid_inclusive_selection(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"; source.write_bytes(b"0123456789")
    widget = page(); widget.update_analysis(result(source))
    assert not widget.extract_button.isEnabled()
    widget.start_input.setText("0x2"); widget.end_input.setText("5")
    assert widget.selected_range() == (2, 5, 4)
    assert widget.extract_button.isEnabled() and "4 bytes selecionados" in widget.range_status.text()
    widget.end_input.setText("99")
    assert not widget.extract_button.isEnabled() and "dentro do arquivo" in widget.range_status.text()


def test_hash_type_and_extraction_feedback(qt_app, tmp_path: Path) -> None:
    jpeg = b"\xff\xd8\xff\xe0\0\x02\xff\xd9"; source = tmp_path / "source.bin"
    source.write_bytes(b"xx" + jpeg + b"yy"); destination = tmp_path / "selection.jpg"
    widget = page(); widget.update_analysis(result(source)); widget.start_input.setText("2")
    widget.end_input.setText(str(2 + len(jpeg) - 1))
    widget.calculate_selection_hash(); assert "SHA-256 da seleção" in widget.feedback.text()
    widget.detect_selection_type(); assert "JPEG" in widget.feedback.text()
    widget._choose_destination = lambda _name: destination
    widget.extract_selection()
    assert destination.read_bytes() == jpeg and widget.last_artifact is not None
    assert "sucesso" in widget.feedback.text() and source.read_bytes() == b"xx" + jpeg + b"yy"


def test_cancel_save_does_not_create_artifact(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "source.bin"; source.write_bytes(b"abcdef")
    widget = page(); widget.update_analysis(result(source)); widget.start_input.setText("0"); widget.end_input.setText("2")
    widget._choose_destination = lambda _name: None; widget.extract_selection()
    assert widget.last_artifact is None and "cancelada" in widget.feedback.text()


def test_large_selection_requires_confirmation(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "large.bin"; source.write_bytes(b"x" * 32)
    widget = page(); widget.LARGE_EXTRACTION_BYTES = 4; widget.update_analysis(result(source))
    widget.start_input.setText("0"); widget.end_input.setText("7")
    called = []; widget._confirm_large_extraction = lambda length: called.append(length) or False
    widget._choose_destination = lambda _name: pytest.fail("save dialog must not open")
    widget.extract_selection(); assert called == [8] and widget.last_artifact is None


def test_file_change_clears_selection_and_stale_callback(qt_app, tmp_path: Path) -> None:
    first = tmp_path / "first.bin"; second = tmp_path / "second.bin"
    first.write_bytes(b"first-data"); second.write_bytes(b"second-data")
    pending = []; widget = MagicNumberPage()
    widget._submit = lambda operation, success, failure: pending.append((operation, success, failure))
    widget.update_analysis(result(first)); old_operation, old_success, _ = pending[-1]
    widget.start_input.setText("0"); widget.end_input.setText("2")
    widget.update_analysis(result(second)); old_success(old_operation())
    assert not widget.start_input.text() and widget._source_path == second
    assert widget.hex_viewer.cached_window_count == 0


def test_virtual_hex_reads_only_requested_windows(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "large.bin"; source.write_bytes(bytes(range(256)) * 1024)
    widget = page(); widget.update_analysis(result(source))
    assert widget.hex_viewer.loaded_bytes == widget.INITIAL_HEX_BYTES
    widget.hex_viewer.go_to_offset(100_000)
    assert widget.hex_viewer.cached_window_count == 2
    assert widget.hex_viewer.loaded_bytes == widget.INITIAL_HEX_BYTES * 2


def test_current_file_is_persistent_and_changes_immediately(qt_app, tmp_path: Path) -> None:
    first = tmp_path / "first-evidence.pdf"; second = tmp_path / "second-evidence.jpg"
    first.write_bytes(b"%PDF-1.7\n%%EOF"); second.write_bytes(b"\xff\xd8\xff\xe0\0\x02\xff\xd9")
    widget = page(); widget.update_analysis(result(first))
    assert widget.file_value.text() == first.name and not widget.file_value.isHidden()
    widget.start_input.setText("0"); widget.end_input.setText("2")
    widget.update_analysis(result(second))
    assert widget.file_value.text() == second.name
    assert not widget.start_input.text() and widget.selection_status.text() == "Selection: none"


def test_click_selection_updates_compact_bar_and_visual_highlight(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "bytes.bin"; source.write_bytes(bytes(range(64)))
    widget = page(); widget.update_analysis(result(source))
    widget.hex_viewer.set_selection(3, 9)
    assert widget.selected_range() == (3, 9, 7)
    assert "7 bytes" in widget.selection_status.text()
    assert widget.hex_viewer.selection_start == 3 and widget.hex_viewer.selection_end == 9


def test_go_to_offset_loads_a_bounded_window_and_rejects_invalid_input(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "large.bin"; source.write_bytes(bytes(range(256)) * 1024)
    widget = page(); widget.update_analysis(result(source))
    widget.goto_input.setText("0x10021"); widget.go_to_offset()
    assert widget.hex_viewer.current_offset == 0x10021
    assert widget.hex_viewer.cached_window_count <= widget.hex_viewer.CACHE_WINDOWS
    assert widget.offset_status.text() == "Offset: 0x00010021"
    widget.goto_input.setText(hex(source.stat().st_size)); widget.go_to_offset()
    assert "outside file bounds" in widget.feedback.text()
    widget.goto_input.setText("-1"); widget.go_to_offset()
    assert "outside file bounds" in widget.feedback.text()


@pytest.mark.parametrize("tokens", [LIGHT_THEME, DARK_THEME])
def test_hex_theme_uses_semantic_palette_without_crashing(qt_app, tokens) -> None:
    widget = page()
    qt_app.setStyleSheet(load_desktop_stylesheet(ApplicationPaths.discover(), tokens))
    widget.apply_theme(tokens)
    palette = widget.hex_viewer.palette()
    assert palette.color(QPalette.Base).name() == tokens.hex_background.lower()
    assert palette.color(QPalette.Text).name() == tokens.hex_text.lower()
    assert palette.color(QPalette.Highlight).name() == tokens.hex_selection.lower()
    assert palette.color(QPalette.Link).name() == tokens.hex_current.lower()
    qt_app.setStyleSheet(load_desktop_stylesheet(ApplicationPaths.discover(), LIGHT_THEME))


def test_empty_and_unavailable_evidence_have_neutral_sanitized_states(qt_app, tmp_path: Path) -> None:
    empty = tmp_path / "empty.bin"; empty.write_bytes(b"")
    widget = page(); widget.update_analysis(result(empty))
    assert widget.hex_viewer.file_size == 0
    assert widget.hex_viewer._empty_message == "Arquivo vazio"

    missing = tmp_path / "private-location" / "missing.bin"
    widget._show_hex_error("unavailable", f"failed to open {missing}")
    assert str(missing) not in widget.hex_viewer._error
    assert "Não foi possível ler" in widget.hex_viewer._error


def test_hex_interaction_never_modifies_source_evidence(qt_app, tmp_path: Path) -> None:
    source = tmp_path / "immutable-evidence.bin"
    source.write_bytes(bytes(range(256)) * 512)
    before = sha256(source.read_bytes()).hexdigest()
    widget = page(); widget.update_analysis(result(source))
    widget.goto_input.setText("0x10021"); widget.go_to_offset()
    widget.hex_viewer.set_selection(0x10020, 0x10023)
    widget.copy_selected_bytes(); widget.copy_selected_ascii()
    widget.close()
    after = sha256(source.read_bytes()).hexdigest()
    assert after == before


def test_long_filename_keeps_full_context_and_narrow_layout(qt_app, tmp_path: Path) -> None:
    long_name = f"{'technical_evidence_' * 8}.bin"
    source = tmp_path / long_name; source.write_bytes(b"evidence")
    widget = page(); widget.update_analysis(result(source)); widget.resize(700, 640); widget.show()
    qt_app.processEvents()
    assert widget.file_value.toolTip() == long_name
    assert not widget.byte_inspector.isVisibleTo(widget)
    assert widget.hex_viewer.horizontalScrollBarPolicy() == Qt.ScrollBarAsNeeded
    assert not widget.findChildren(QScrollArea)
    widget.hide()


@pytest.mark.parametrize("width,height", [(960, 640), (1366, 768), (1920, 1080)])
def test_hex_workspace_remains_dominant_at_supported_sizes(qt_app, tmp_path: Path,
                                                           width: int, height: int) -> None:
    source = tmp_path / f"view-{width}.bin"; source.write_bytes(bytes(range(128)))
    widget = page(); widget.update_analysis(result(source)); widget.resize(width, height); widget.show()
    qt_app.processEvents()
    assert widget.width() == width and widget.height() >= height - 24
    assert widget.hex_workspace.width() >= width - 32
    assert widget.hex_workspace.height() >= int(widget.height() * 0.55)
    assert widget.hex_viewer.isVisibleTo(widget)
    assert widget.byte_inspector.width() <= 168
    assert widget.hex_viewer.width() > widget.byte_inspector.width() * 4
    geometry = widget.hex_viewer.grid_geometry()
    assert geometry.hex_rect.width() > geometry.ascii_rect.width() * 3
    assert geometry.ascii_rect.right() <= widget.hex_viewer.viewport().width()
    assert widget.hex_viewer.cell_rect(15).right() <= geometry.hex_rect.right()
    assert widget.selection_bar.isVisibleTo(widget) and widget.status_bar.isVisibleTo(widget)
    assert widget.extract_button.isVisibleTo(widget)
    assert not widget.findChildren(QScrollArea)
    widget.hide()

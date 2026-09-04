from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from app.models import (
    AnalysisResult,
    DigitalSignatureResult,
    FileInfo,
    HashResult,
    MagicNumberResult,
    MetadataResult,
)
from app.ui.main_window import MainWindow
from app.models.integrity_result import IntegrityResult


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


class AnalysisServiceSpy:
    def __init__(self) -> None:
        self.analyze_calls: list[Path] = []

    def analyze(self, path: Path):
        self.analyze_calls.append(path)
        raise AssertionError("selection must not analyze files")


def _result(path: Path, marker: str) -> AnalysisResult:
    return AnalysisResult(
        file_info=FileInfo(path.name, path, path.suffix, path.stat().st_size, datetime.now()),
        hashes=HashResult(marker, marker, marker, marker, marker, marker),
        metadata=MetadataResult({"marker": marker}),
        findings=[],
        magic_numbers=MagicNumberResult(
            "PDF Document", "25 50 44 46", True,
            detected_format="PDF", mime_type="application/pdf",
        ),
        digital_signature=DigitalSignatureResult(False),
        integrity=IntegrityResult(
            score=0,
            technical_status="Estado factual",
            is_structurally_valid=True,
            hash_verified=True,
            magic_number_verified=True,
            digital_signature_present=False,
            header_valid=True,
            eof_valid=True,
            encrypted=False,
            javascript_detected=False,
            embedded_files=False,
            xref_valid=True,
            trailer_valid=True,
            incremental_updates=0,
        ),
    )


def _window(tmp_path: Path, names: tuple[str, ...] = ("a.pdf", "b.pdf", "c.pdf")):
    service = AnalysisServiceSpy()
    window = MainWindow(service)
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(name.encode())
        paths.append(path)
    window.current_folder_path = tmp_path
    window.file_strip.set_files(paths)
    window._case_file_states = {str(path.resolve()): "pending" for path in paths}
    window._case_progress = {
        "case_name": tmp_path.name, "is_case": True, "total": len(paths),
        "analyzed": 0, "analyzing": 0, "pending": len(paths), "failed": 0,
        "current_file": "", "file_paths": [str(path) for path in paths],
    }
    return window, service, paths


def _select(window: MainWindow, index: int) -> None:
    raw = window.file_strip.model.index(index).data(window.file_strip.model.PathRole)
    window.select_file_from_strip(Path(str(raw)))


def _seed(window: MainWindow, results: list[AnalysisResult]) -> None:
    case_id = str(window.current_folder_path.resolve())
    window.analysis_results = list(results)
    window._case_result_cache[case_id] = {
        str(Path(result.file_info.path).resolve()): result for result in results
    }
    for result in results:
        window._case_file_states[str(Path(result.file_info.path).resolve())] = "analyzed"


def test_selects_cached_a_then_b_then_a_without_analysis(qt_app, tmp_path: Path) -> None:
    window, service, paths = _window(tmp_path)
    a, b = _result(paths[0], "A"), _result(paths[1], "B")
    _seed(window, [a, b])

    _select(window, 0)
    assert window.current_result is a
    _select(window, 1)
    assert window.current_result is b
    _select(window, 0)
    assert window.current_result is a
    assert service.analyze_calls == []
    window.close()


def test_pending_clears_stale_result_and_completion_updates_if_still_selected(
    qt_app, tmp_path: Path,
) -> None:
    window, _service, paths = _window(tmp_path)
    a, c = _result(paths[0], "A"), _result(paths[2], "C")
    _seed(window, [a])
    _select(window, 0)
    _select(window, 2)

    assert window.current_result is None
    assert window.current_selection.status == "pending"
    assert window.workspace.deep_file_explorer_page._result is None
    assert "Pendente" in window.workspace.selection_placeholder.text()

    window._on_file_analyzed(c)
    assert window.current_result is c
    assert window.workspace.deep_file_explorer_page._result is c
    window.close()


def test_completion_of_other_file_does_not_steal_selection(qt_app, tmp_path: Path) -> None:
    window, _service, paths = _window(tmp_path)
    b, c = _result(paths[1], "B"), _result(paths[2], "C")
    _seed(window, [b])
    _select(window, 1)

    window._on_file_analyzed(c)

    assert window.current_result is b
    assert window.current_selection.file_path == paths[1]
    assert window.workspace.deep_file_explorer_page._result is b
    window.close()


def test_failed_selection_clears_stale_result_and_reports_failure(qt_app, tmp_path: Path) -> None:
    window, _service, paths = _window(tmp_path)
    a = _result(paths[0], "A")
    _seed(window, [a])
    window._case_file_states[str(paths[1].resolve())] = "failed"
    window._case_file_errors[str(paths[1].resolve())] = "parser unavailable"
    _select(window, 0)
    _select(window, 1)

    assert window.current_result is None
    assert window.current_selection.status == "failed"
    assert "Falha na análise" in window.workspace.selection_placeholder.text()
    assert "parser unavailable" in window.workspace.selection_placeholder.text()
    assert window.workspace.deep_file_explorer_page._result is None
    window.close()


def test_deep_explorer_tracks_a_b_a(qt_app, tmp_path: Path) -> None:
    window, _service, paths = _window(tmp_path)
    a, b = _result(paths[0], "A"), _result(paths[1], "B")
    _seed(window, [a, b])

    for index, expected in ((0, a), (1, b), (0, a)):
        _select(window, index)
        assert window.workspace.deep_file_explorer_page._result is expected
        assert Path(window.workspace.deep_file_explorer_page._result.file_info.path) == paths[index]
    window.close()


def test_selection_does_not_mutate_case_or_correlation(qt_app, tmp_path: Path) -> None:
    window, service, paths = _window(tmp_path)
    a, b = _result(paths[0], "A"), _result(paths[1], "B")
    _seed(window, [a, b])
    window.correlation_result = SimpleNamespace(total_findings=2, findings=("one", "two"))
    before = (
        len(window.analysis_results),
        len(window._case_result_cache[str(tmp_path.resolve())]),
        len(window.correlation_result.findings),
    )

    _select(window, 0)
    _select(window, 1)
    _select(window, 0)

    assert before == (
        len(window.analysis_results),
        len(window._case_result_cache[str(tmp_path.resolve())]),
        len(window.correlation_result.findings),
    )
    assert service.analyze_calls == []
    window.close()

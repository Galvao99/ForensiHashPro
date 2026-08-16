from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QSplitter

from app.engines.comparison_engine import ComparisonEngine
from app.models import (
    AnalysisResult, DigitalSignatureResult, FileInfo, HashResult,
    MagicNumberResult, MetadataResult,
)
from app.models.integrity_result import IntegrityResult
from app.pages.comparison_workspace import ComparisonWorkspace
from app.services.comparison_service import ComparisonService, artifact_id
from app.ui.sidebar import Sidebar


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def result(name: str, path: str, sha256: str, *, author: str = "Autor") -> AnalysisResult:
    return AnalysisResult(
        file_info=FileInfo(name, Path(path), ".pdf", 842_000, datetime.now()),
        hashes=HashResult("md5", "sha1", "sha224", sha256, "sha384", "sha512"),
        metadata=MetadataResult({"Author": author, "Producer": "PDFium"}),
        findings=[],
        magic_numbers=MagicNumberResult("PDF", "25504446", True, detected_format="PDF"),
        digital_signature=DigitalSignatureResult(False),
        integrity=IntegrityResult(
            score=0, technical_status="Factual", is_structurally_valid=True,
            hash_verified=True, magic_number_verified=True, digital_signature_present=False,
        ),
        analysis_id=path,
        extracted_text="linha comum\ntexto A",
    )


class CountingEngine(ComparisonEngine):
    def __init__(self) -> None:
        self.calls = 0

    def compare(self, left, right):
        self.calls += 1
        return super().compare(left, right)


def visible_text(widget) -> str:
    return "\n".join(label.text() for label in widget.findChildren(QLabel))


def test_one_artifact_requests_another_without_error(qt_app) -> None:
    page = ComparisonWorkspace(object())
    page.update_results([result("contrato.pdf", "a/contrato.pdf", "a")])
    assert "Adicione outro artefato" in page.empty_message.text()
    assert not page.execute_button.isEnabled()


def test_selects_exact_pair_and_executes_once(qt_app) -> None:
    engine = CountingEngine()
    page = ComparisonWorkspace(object(), ComparisonService(engine))
    items = [result("a.pdf", "a/a.pdf", "same"), result("b.pdf", "b/b.pdf", "same")]
    page.update_results(items)
    page.nodes[artifact_id(items[0])].click()
    page.nodes[artifact_id(items[1])].click()
    assert page.selected_ids == [artifact_id(items[0]), artifact_id(items[1])]
    assert page.execute_button.isEnabled()
    assert engine.calls == 0
    page.execute_button.click()
    assert engine.calls == 1
    assert page.comparison_result is not None
    text = visible_text(page.result_page).casefold()
    assert "sha-256 dos artefatos correspondente" in text
    assert "before" not in text and "after" not in text


def test_third_artifact_does_not_replace_pair(qt_app, monkeypatch) -> None:
    page = ComparisonWorkspace(object())
    items = [result(f"{letter}.pdf", f"{letter}/{letter}.pdf", letter) for letter in "abc"]
    page.update_results(items)
    monkeypatch.setattr("app.pages.comparison_workspace.QMessageBox.information", lambda *args: None)
    for item in items:
        page.nodes[artifact_id(item)].click()
    assert page.selected_ids == [artifact_id(items[0]), artifact_id(items[1])]


def test_same_filename_has_distinct_identity(qt_app) -> None:
    a = result("contrato.pdf", "pasta-a/contrato.pdf", "a")
    b = result("contrato.pdf", "pasta-b/contrato.pdf", "b")
    page = ComparisonWorkspace(object())
    page.update_results([a, b])
    assert artifact_id(a) != artifact_id(b)
    assert len(page.nodes) == 2


def test_matches_only_include_equal_values_and_hash(qt_app) -> None:
    service = ComparisonService()
    a = result("a.pdf", "a", "equal", author="Mesmo")
    b = result("b.pdf", "b", "equal", author="Mesmo")
    b = replace(b, metadata=MetadataResult({"Author": "Mesmo", "Producer": "Outro"}))
    view = service.compare(a, b)
    matches = {(group, key, value) for group, key, value in view.matches}
    assert ("Metadados", "Author", "Mesmo") in matches
    assert not any(key == "Producer" for _, key, _ in matches)
    assert ("Hashes", "SHA256", "equal") in matches
    metadata = next(group for group in view.groups if group.title == "Metadados")
    assert next(field for field in metadata.fields if field.key == "Producer").state == "changed"


def test_back_preserves_artifacts_and_pair_can_change(qt_app) -> None:
    page = ComparisonWorkspace(object())
    items = [result(f"{letter}.pdf", letter, letter) for letter in "abc"]
    page.update_results(items)
    page.nodes[artifact_id(items[0])].click(); page.nodes[artifact_id(items[1])].click()
    page.execute_comparison()
    page.stack.setCurrentWidget(page.workspace_page)
    assert len(page.nodes) == 3 and len(page.selected_ids) == 2
    page.nodes[artifact_id(items[0])].click()
    page.nodes[artifact_id(items[2])].click()
    page.execute_comparison()
    assert page.comparison_result.left_id == artifact_id(items[1])
    assert page.comparison_result.right_id == artifact_id(items[2])


def test_sidebar_collapses_expands_and_keeps_navigation(qt_app) -> None:
    sidebar = Sidebar()
    requested: list[str] = []
    sidebar.navigation_requested.connect(requested.append)
    sidebar.set_collapsed(True)
    assert sidebar.is_collapsed
    assert sidebar.maximumWidth() == 64
    assert sidebar.navigation_buttons["comparison"].isVisibleTo(sidebar)
    sidebar.navigation_buttons["comparison"].click()
    assert requested == ["comparison"]
    sidebar.set_collapsed(False)
    assert not sidebar.is_collapsed
    assert sidebar.minimumWidth() == 260


def test_presentation_controls_do_not_execute_engine_again(qt_app) -> None:
    engine = CountingEngine()
    page = ComparisonWorkspace(object(), ComparisonService(engine))
    items = [result("a.pdf", "a", "same"), result("b.pdf", "b", "same")]
    page.update_results(items)
    for item in items:
        page.nodes[artifact_id(item)].click()
    page.execute_comparison()
    comparison = page.comparison_result
    assert engine.calls == 1
    assert page.findChildren(QSplitter)

    changed = next(button for button in page.filter_group.buttons() if button.property("filter") == "changed")
    changed.click()
    assert page.current_filter == "changed"
    assert page.comparison_result is comparison

    if page.matches_summary.toggle.isVisible():
        page.matches_summary.toggle.click()
        assert page.matches_summary.expanded
        page.matches_summary.toggle.click()
        assert not page.matches_summary.expanded
    assert engine.calls == 1


def test_focus_mode_preserves_pair_and_result(qt_app) -> None:
    page = ComparisonWorkspace(object())
    items = [result("a.pdf", "a", "a"), result("b.pdf", "b", "b")]
    page.update_results(items)
    for item in items:
        page.nodes[artifact_id(item)].click()
    page.execute_comparison()
    comparison = page.comparison_result
    selected = list(page.selected_ids)
    page.set_focus_mode(True)
    page.set_focus_mode(False)
    assert page.comparison_result is comparison
    assert page.selected_ids == selected


def test_technical_matches_are_compact_and_keep_total(qt_app) -> None:
    page = ComparisonWorkspace(object())
    items = [result("a.pdf", "a", "same"), result("b.pdf", "b", "same")]
    page.update_results(items)
    for item in items:
        page.nodes[artifact_id(item)].click()
    page.execute_comparison()
    total = page.comparison_result.match_count
    assert page.matches_summary.count.text() == str(total)
    assert page.matches_summary.rows_layout.count() == min(total, page.matches_summary.INITIAL_LIMIT)
    if total > page.matches_summary.INITIAL_LIMIT:
        page.matches_summary.toggle.click()
        assert page.matches_summary.rows_layout.count() == total
        page.matches_summary.toggle.click()
        assert page.matches_summary.rows_layout.count() == page.matches_summary.INITIAL_LIMIT

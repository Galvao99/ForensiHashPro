from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QSignalSpy
from PySide6.QtWidgets import QApplication, QBoxLayout, QLabel, QProgressBar, QPushButton

from app.entities.models import (
    EntitySource, EntitySourceType, EntityType as ResolvedEntityType, NormalizedEntity,
)
from app.investigation.declared_hash import DeclaredHashExtractor
from app.investigation.investigation_context import InvestigationContext
from app.pages.correlation_explorer_page import CorrelationExplorerPage
from app.presentation.correlation_explorer import (
    CorrelationExplorerModel, ExplorerElement, ExplorerOccurrence,
    build_case_correlation_summary, build_correlation_explorer_model,
    compact_hash, filter_correlation_elements,
    format_temporal_ptbr, presentation_field_label,
)
from app.presentation.file_type_icons import file_type_icon_name
from app.ui.sidebar import Sidebar
from app.widgets.analysis_workspace import AnalysisWorkspace
from app.correlation.case_result import (
    CaseFinding, CaseResult, EpistemicState, RuleExecutionLimitation,
)
from app.correlation.v2.engine import EvidenceGraphCorrelationEngine
from app.correlation.v2.index import CaseEvidenceIndex
from app.correlation.v2.pipeline import CanonicalCasePipeline, CanonicalCasePipelineResult
from app.correlation.v2.providers import InvestigationContextCorrelationProvider
from app.processing import ProcessingStatus
from app.enum.severity import Severity
from app.models.json_analysis_result import JsonAnalysisResult, JsonField
from app.settings import ApplicationPaths
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _entity(value: str, file_name: str, source_type=EntitySourceType.NATIVE_TEXT):
    source = EntitySource(
        source_type, file_name, page=1, start=5, end=19,
        context_before="CPF: ", extractor="resolver",
    )
    return NormalizedEntity(
        ResolvedEntityType.CPF, value, 1.0, (value,), (source,),
    )


def _result(
    tmp_path: Path, name: str, *, cpf: str | None = None,
    digest: str = "a" * 64, json_analysis: JsonAnalysisResult | None = None,
):
    entities = [_entity(cpf, name)] if cpf else []
    return SimpleNamespace(
        file_info=SimpleNamespace(name=name, path=tmp_path / name),
        hashes=SimpleNamespace(sha256=digest, md5=digest[:32]),
        metadata=SimpleNamespace(raw={}), resolved_entities=entities,
        processing_steps=(), extracted_text="",
        timeline_events=(), evidence_source=None, json_analysis=json_analysis,
    )


def _snapshot(results, case_id: str = "case-1") -> CanonicalCasePipelineResult:
    return CanonicalCasePipeline().analyze(case_id, results)


def _context_snapshot(results, context: InvestigationContext) -> CanonicalCasePipelineResult:
    candidates = InvestigationContextCorrelationProvider().provide_many(context, results)
    report = EvidenceGraphCorrelationEngine().correlate(candidates)
    return CanonicalCasePipelineResult(report, CaseEvidenceIndex(report), CaseResult("case-1"))


def _manifest(filename: str, digest: str) -> JsonAnalysisResult:
    return JsonAnalysisResult(is_valid=True, fields=[
        JsonField("$.entry.filename", "filename", filename, "string"),
        JsonField("$.entry.sha256", "sha256", digest, "string"),
    ])


def test_same_identifier_is_observation_not_same_document(tmp_path: Path) -> None:
    model = build_correlation_explorer_model(_snapshot([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
        _result(tmp_path, "b.pdf", cpf="52998224725"),
    ]))
    cpf = next(item for item in model.elements if item.type_label == "CPF")
    assert cpf.artifact_count == 2
    assert cpf.relation_label == "Mesmo valor normalizado observado"
    assert cpf.deterministic_state is None
    assert "documento" not in cpf.relation_label.casefold()


def test_counts_provenance_and_frequency_are_descriptive(tmp_path: Path) -> None:
    model = build_correlation_explorer_model(_snapshot([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
        _result(tmp_path, "b.pdf", cpf="52998224725"),
    ]))
    cpf = next(item for item in model.elements if item.type_label == "CPF")
    assert (cpf.artifact_count, cpf.occurrence_count) == (2, 2)
    assert cpf.occurrences[0].page == 1
    assert "Página 1" in cpf.occurrences[0].provenance_label
    ordered = filter_correlation_elements(model.elements, sort_by="occurrences")
    assert {item.deterministic_state for item in ordered if item.type_label == "CPF"} == {None}


def test_calculated_hash_match_is_deterministic_and_source_typed(tmp_path: Path) -> None:
    digest = "d" * 64
    model = build_correlation_explorer_model(_snapshot([
        _result(tmp_path, "a.bin", digest=digest),
        _result(tmp_path, "b.bin", digest=digest),
    ]))
    sha = next(item for item in model.elements if item.type_label == "SHA-256")
    assert sha.deterministic_state == "MATCH"
    assert {item.source_kind for item in sha.occurrences} == {"calculated_hash"}


def test_declared_and_hash_like_values_are_not_calculated_match(tmp_path: Path) -> None:
    declared = DeclaredHashExtractor().extract_text(
        f"SHA-256: {'e' * 64}", evidence_ref="a", filename="a.pdf",
        source_type="native_text", page=3,
    )
    hash_like = DeclaredHashExtractor().extract_text(
        "f" * 64, evidence_ref="b", filename="b.pdf", source_type="ocr", page=2,
    )
    context = InvestigationContext(declared_hashes={"a.pdf": declared, "b.pdf": hash_like})
    results = [_result(tmp_path, "a.pdf", digest="a" * 64),
               _result(tmp_path, "b.pdf", digest="b" * 64)]
    model = build_correlation_explorer_model(_context_snapshot(results, context))
    observed = [item for item in model.elements if "compatível" in item.type_label or "declarado" in item.type_label]
    assert {item.occurrences[0].source_kind for item in observed} == {"declared_hash", "hash_like"}
    assert all(item.deterministic_state is None for item in observed)


def test_producer_distribution_is_neutral(tmp_path: Path) -> None:
    context = InvestigationContext(
        producers={"a.pdf": "Adobe Acrobat", "b.pdf": "LibreOffice"},
        creators={"a.pdf": "Editor X"},
    )
    results = [_result(tmp_path, "a.pdf"), _result(tmp_path, "b.pdf")]
    model = build_correlation_explorer_model(_context_snapshot(results, context))
    producers = [item for item in model.elements if item.type_label == "Produtor"]
    assert len(producers) == 2
    assert all(item.deterministic_state is None for item in producers)
    assert all("alert" not in item.relation_label.casefold() for item in producers)


def test_search_normalizes_spacing_and_does_not_mutate_model(tmp_path: Path) -> None:
    model = build_correlation_explorer_model(_snapshot([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
    ]))
    before = model.elements
    matches = filter_correlation_elements(model.elements, "529.982.247-25")
    assert any(item.type_label == "CPF" for item in matches)
    assert model.elements is before


def test_routes_remain_separate_and_comparison_is_renamed(qt_app) -> None:
    sidebar = Sidebar()
    labels = {key: label for _group, _title, items in sidebar.GROUPS for key, _icon, label in items}
    assert labels["correlations"] == "Correlações"
    assert labels["comparison"] == "Comparação"
    assert sidebar.navigation_buttons["correlations"] is not sidebar.navigation_buttons["comparison"]


def test_page_update_is_cached_and_detail_navigation_is_explicit(qt_app, tmp_path: Path, monkeypatch) -> None:
    result = _result(tmp_path, "a.pdf", cpf="52998224725")
    page = CorrelationExplorerPage()
    calls = 0
    original = build_correlation_explorer_model

    def tracked(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr("app.pages.correlation_explorer_page.build_correlation_explorer_model", tracked)
    snapshot = _snapshot([result])
    page.update_case("case-1", [result], snapshot)
    page.update_case("case-1", [result], snapshot)
    assert calls == 1
    assert page._model.elements


def test_page_does_not_duplicate_shell_title(qt_app) -> None:
    page = CorrelationExplorerPage()
    assert AnalysisWorkspace.PAGE_TITLES["correlations"] == "Correlações"
    assert not any(label.text() == "Correlações" for label in page.findChildren(QLabel))
    assert any(
        label.text() == "Visão consolidada das relações técnicas observadas entre os artefatos deste Caso."
        for label in page.findChildren(QLabel)
    )


@pytest.mark.parametrize(("key", "label"), [
    ("accessed_at", "Data de acesso"), ("created_at", "Data de criação"),
    ("modified_at", "Data de modificação"), ("Producer", "Produtor"),
    ("Creator", "Criador"),
])
def test_known_internal_fields_have_ptbr_presentation(key: str, label: str) -> None:
    assert presentation_field_label(key) == label
    assert key not in presentation_field_label(key) or key == label


@pytest.mark.parametrize(("filename", "icon"), [
    ("documento.pdf", "file-type-pdf"), ("foto.jpeg", "file-type-jpg"),
    ("imagem.png", "file-type-png"), ("dados.json", "braces"),
    ("dados.sql", "file-type-sql"),
    ("tabela.csv", "file-type-csv"), ("texto.txt", "file-type-txt"),
    ("pacote.zip", "file-type-zip"), ("oficio.docx", "file-type-docx"),
    ("planilha.xlsx", "file-type-xls"), ("slides.pptx", "file-type-ppt"),
    ("dados.xml", "file-type-xml"), ("pagina.html", "file-type-html"),
    ("mensagem.eml", "mail"), ("mensagem.msg", "mail"),
])
def test_file_type_icon_mapping(filename: str, icon: str) -> None:
    assert file_type_icon_name(filename) == icon


def test_unknown_file_icon_uses_safe_generic_fallback() -> None:
    assert file_type_icon_name("evidencia.xyz") == "file"


def test_temporal_ptbr_format_preserves_timezone_semantics() -> None:
    raw = "2023-01-26T18:50:30+00:00"
    assert format_temporal_ptbr(raw) == "26/01/2023 · 18:50:30 UTC"
    assert format_temporal_ptbr("2023-01-26T18:50:30") == "26/01/2023 · 18:50:30"
    assert format_temporal_ptbr("2023-01") == "01/2023"


def test_long_hash_is_only_compacted_for_list_presentation() -> None:
    value = "b570c5" + "a" * 52 + "c5f1aa"
    assert compact_hash(value) == "b570c5…c5f1aa"
    assert len(value) == 64


def _ui_element(index: int = 0) -> ExplorerElement:
    occurrence = ExplorerOccurrence(
        f"occ-{index}", f"file-{index}", f"arquivo-{index}.pdf",
        f"C:/case/arquivo-{index}.pdf", "529.982.247-25", "52998224725",
        "Texto nativo", "Texto nativo · Página 2", "text_extraction", page=2,
    )
    return ExplorerElement(
        f"entity-{index}", "identifiers", "CPF", "529.982.247-25",
        "52998224725", (occurrence,), "Valor técnico observado", None,
    )


def test_selection_renders_detail_and_deep_link_remains_optional(qt_app) -> None:
    page = CorrelationExplorerPage()
    element = _ui_element()
    page._model = CorrelationExplorerModel((element,))
    page._refresh_list()
    assert not page.findChildren(QPushButton, "InlineActionButton")
    page._select(element)
    texts = [label.text() for label in page.detail_content.findChildren(QLabel)]
    assert "CPF" in texts
    assert "1 artefato · 1 ocorrência" in texts
    assert "Valor técnico observado" in texts
    assert page.findChildren(QPushButton, "InlineActionButton")
    assert element.deterministic_state is None


def test_long_correlation_list_scrolls_without_clipping(qt_app) -> None:
    page = CorrelationExplorerPage()
    page.resize(1000, 480)
    page._model = CorrelationExplorerModel(tuple(
        _element_with_occurrences(f"entity-{index}", "identifiers", [f"a-{index}", f"b-{index}"])
        for index in range(40)
    ))
    page._summary = build_case_correlation_summary(page._model, [])
    page._refresh_list()
    page.show_explorer()
    page.show()
    qt_app.processEvents()
    assert page.list_scroll.verticalScrollBar().maximum() > 0
    assert page.splitter.sizes()[0] < page.splitter.sizes()[1]
    for button in page._element_buttons.values():
        children_bottom = max(label.geometry().bottom() for label in button.findChildren(QLabel))
        assert button.height() >= button.minimumSizeHint().height() > 24
        assert children_bottom < button.height()
    page.close()


def _element_with_occurrences(stable_id: str, category: str, artifact_ids: list[str]) -> ExplorerElement:
    occurrences = tuple(
        ExplorerOccurrence(
            f"{stable_id}-occ-{index}", artifact_id, f"{artifact_id}.pdf",
            f"C:/case/{artifact_id}.pdf", stable_id, stable_id,
            "Corpo do documento", "Corpo do documento · Página 1", "text_extraction", page=1,
        )
        for index, artifact_id in enumerate(artifact_ids)
    )
    return ExplorerElement(
        stable_id, category, "CPF", stable_id, stable_id, occurrences,
        "Mesmo valor normalizado observado" if len(set(artifact_ids)) > 1 else "Valor técnico observado",
    )


def test_summary_excludes_one_occurrence_in_one_artifact(tmp_path: Path) -> None:
    element = _element_with_occurrences("one", "identifiers", ["a"])
    summary = build_case_correlation_summary(
        CorrelationExplorerModel((element,)), [_result(tmp_path, "a.pdf")],
    )
    assert summary.correlated_element_count == 0
    assert not summary.correlated_element_ids


def test_repeated_occurrences_in_same_artifact_are_not_cross_artifact(tmp_path: Path) -> None:
    element = _element_with_occurrences("repeat", "other", ["a"] * 84)
    summary = build_case_correlation_summary(
        CorrelationExplorerModel((element,)), [_result(tmp_path, "a.pdf")],
    )
    assert element.occurrence_count == 84
    assert element.artifact_count == 1
    assert summary.correlated_element_count == 0
    assert summary.categories == ()


@pytest.mark.parametrize("artifact_ids", [["a", "b"], ["a", "b", "c", "d", "e"]])
def test_same_value_across_distinct_artifacts_counts_once(tmp_path: Path, artifact_ids: list[str]) -> None:
    element = _element_with_occurrences("cpf-x", "identifiers", artifact_ids)
    results = [_result(tmp_path, f"{artifact_id}.pdf") for artifact_id in artifact_ids]
    summary = build_case_correlation_summary(CorrelationExplorerModel((element,)), results)
    assert summary.correlated_element_count == 1
    assert summary.participating_artifact_count == len(artifact_ids)
    assert summary.categories[0].element_count == 1


def test_category_summary_counts_elements_not_occurrences(tmp_path: Path) -> None:
    cpf = _element_with_occurrences("cpf", "identifiers", ["a", "b", "b"])
    temporal = _element_with_occurrences("date", "temporal", ["a", "b", "a", "b"])
    noise = _element_with_occurrences("money", "other", ["a"] * 50)
    summary = build_case_correlation_summary(
        CorrelationExplorerModel((cpf, temporal, noise)),
        [_result(tmp_path, "a.pdf"), _result(tmp_path, "b.pdf"), _result(tmp_path, "c.pdf")],
    )
    assert summary.correlated_element_count == 2
    assert [(item.label, item.element_count) for item in summary.categories] == [
        ("Identificadores e identidades", 1), ("Temporal", 1),
    ]
    assert summary.artifact_without_relation_count == 1


def test_only_canonical_findings_create_cross_source_verifications(tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.bin", digest="d" * 64),
               _result(tmp_path, "b.bin", digest="d" * 64)]
    model = build_correlation_explorer_model(_snapshot(results))
    summary = build_case_correlation_summary(model, results)
    group = summary.verification_groups[0]
    assert group.label == "Hashes calculados idênticos"
    assert group.items[0].state == "MATCH"
    assert len(group.items[0].supporting_occurrences) == 2


def test_different_dates_without_applicable_rule_never_become_divergent(tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.pdf", digest="a" * 64),
               _result(tmp_path, "b.pdf", digest="b" * 64)]
    model = build_correlation_explorer_model(_snapshot(results))
    summary = build_case_correlation_summary(model, results)
    assert summary.verification_groups == ()


def test_missing_canonical_verification_never_manufactures_mismatch(tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.pdf", digest="a" * 64),
               _result(tmp_path, "b.pdf", digest="b" * 64)]
    model = build_correlation_explorer_model(_snapshot(results))
    assert not model.verification_groups
    assert all(item.deterministic_state is None for item in model.elements)


def test_summary_explorer_back_preserves_state_without_rebuilding(qt_app) -> None:
    page = CorrelationExplorerPage()
    element = _element_with_occurrences("cpf", "identifiers", ["a", "b"])
    page._model = CorrelationExplorerModel((element,))
    page._summary = build_case_correlation_summary(page._model, [])
    page.search.setText("cpf")
    page._selected_id = element.stable_id
    model_identity = id(page._model)
    page.show_explorer("identities")
    assert page.content_stack.currentWidget() is page.explorer_view
    assert page._summary_category_scope == frozenset({"identifiers", "identities"})
    page.show_summary()
    assert page.content_stack.currentWidget() is page.summary_view
    assert page.search.text() == "cpf"
    assert page._selected_id == element.stable_id
    assert id(page._model) == model_identity


def test_summary_visible_text_is_ptbr(qt_app) -> None:
    page = CorrelationExplorerPage()
    page._render_summary()
    text = "\n".join(label.text() for label in page.summary_view.findChildren(QLabel))
    buttons = "\n".join(button.text() for button in page.summary_view.findChildren(QPushButton))
    assert "Visão consolidada" in text
    assert "relevância pericial" in text
    assert "Nenhum caso selecionado" in text
    assert "Ver todos os elementos" not in buttons


def test_summary_is_default_and_primary_metric_opens_all_elements(qt_app, tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.pdf", cpf="52998224725"),
               _result(tmp_path, "b.pdf", cpf="52998224725")]
    page = CorrelationExplorerPage(); page.update_case("case-1", results, _snapshot(results))
    assert page.content_stack.currentWidget() is page.summary_view
    metric = page.findChild(QPushButton, "CorrelationMetricButton")
    assert metric is not None
    assert metric.text().startswith(f"{page._summary.correlated_element_count}\n")
    metric.click()
    assert page.content_stack.currentWidget() is page.explorer_view
    assert len(page._element_buttons) == page._summary.correlated_element_count


def test_category_microbar_has_exact_count_and_opens_filtered_explorer(qt_app, tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.pdf", cpf="52998224725"),
               _result(tmp_path, "b.pdf", cpf="52998224725")]
    page = CorrelationExplorerPage(); page.update_case("case-1", results, _snapshot(results))
    bar = page.findChild(QProgressBar, "CorrelationCategoryBar")
    count = page.findChild(QLabel, "CorrelationCategoryCount")
    row = page.findChild(QPushButton, "CorrelationSummaryRow")
    assert bar is not None and bar.value() == 1
    assert count is not None and count.text() == "1"
    assert row is not None
    row.click()
    assert page.content_stack.currentWidget() is page.explorer_view
    assert page._summary_category_scope == frozenset({"identifiers", "identities"})


def test_search_and_filter_only_use_qualifying_canonical_elements(qt_app) -> None:
    correlated = _element_with_occurrences("cpf", "identifiers", ["a", "b"])
    isolated = _element_with_occurrences("isolated", "identifiers", ["a"])
    page = CorrelationExplorerPage()
    page._case_id = "case-1"
    page._model = CorrelationExplorerModel((correlated, isolated))
    page._summary = build_case_correlation_summary(page._model, [])
    page.show_explorer("identities")
    page.search.setText("isolated")
    assert not page._element_buttons
    page.search.setText("cpf")
    assert set(page._element_buttons) == {"cpf"}


def test_declared_hash_states_come_only_from_canonical_case_result(tmp_path: Path) -> None:
    digest = "c" * 64
    match_results = [
        _result(tmp_path, "protocol.json", digest="d" * 64,
                json_analysis=_manifest("contract.pdf", digest)),
        _result(tmp_path, "contract.pdf", digest=digest),
    ]
    match_model = build_correlation_explorer_model(_snapshot(match_results))
    declared = next(group for group in match_model.verification_groups if group.key == "declared_hash")
    assert [item.state for item in declared.items] == ["MATCH"]
    assert declared.items[0].relation_id
    assert len(declared.items[0].supporting_occurrences) == 2

    mismatch_results = [
        _result(tmp_path, "manifest.json", digest="e" * 64,
                json_analysis=_manifest("different.pdf", "f" * 64)),
        _result(tmp_path, "different.pdf", digest="0" * 64),
    ]
    mismatch_model = build_correlation_explorer_model(_snapshot(mismatch_results))
    declared = next(group for group in mismatch_model.verification_groups if group.key == "declared_hash")
    assert [item.state for item in declared.items] == ["MISMATCH"]


def test_case_switch_resets_state_and_rejects_stale_snapshot(qt_app, tmp_path: Path) -> None:
    first_results = [_result(tmp_path, "a.pdf", cpf="52998224725"),
                     _result(tmp_path, "b.pdf", cpf="52998224725")]
    second_results = [_result(tmp_path, "c.pdf", digest="c" * 64)]
    first = _snapshot(first_results, "case-a"); second = _snapshot(second_results, "case-b")
    page = CorrelationExplorerPage(); page.update_case("case-a", first_results, first)
    page.show_explorer(); page.search.setText("cpf")
    page.update_case("case-b", second_results, second)
    assert page._case_id == "case-b"
    assert page.content_stack.currentWidget() is page.summary_view
    assert page.search.text() == ""
    page.update_case("case-b", second_results, first)
    assert page._case_id == "case-b" and page._snapshot_fingerprint == id(second)


def test_artifact_navigation_emits_canonical_path_not_filename(qt_app) -> None:
    page = CorrelationExplorerPage(); element = _ui_element(7)
    spy = QSignalSpy(page.artifact_requested)
    page._select(element)
    link = page.findChild(QPushButton, "CorrelationArtifactLink")
    assert link is not None; link.click()
    assert list(spy.at(0)) == [element.occurrences[0].artifact_path]


def test_operational_limitation_is_separate_from_verification(qt_app) -> None:
    report = EvidenceGraphCorrelationEngine().correlate([])
    limitation = RuleExecutionLimitation(
        "case.signing_time_certificate_validity", "1", "unavailable",
        ProcessingStatus.UNAVAILABLE, "A verificação temporal não pôde ser concluída.",
    )
    snapshot = CanonicalCasePipelineResult(
        report, CaseEvidenceIndex(report), CaseResult("case-1", limitations=(limitation,)),
    )
    page = CorrelationExplorerPage(); page.update_case("case-1", [_result(Path("."), "a.pdf")], snapshot)
    text = "\n".join(label.text() for label in page.summary_view.findChildren(QLabel))
    assert "LIMITAÇÕES DE ANÁLISE" in text
    assert "não puderam ser concluídas" in text
    assert not page._summary.verification_groups


def test_signing_time_presentation_is_temporal_not_signature_validity() -> None:
    report = EvidenceGraphCorrelationEngine().correlate([])
    finding = CaseFinding(
        rule_id="case.signing_time_certificate_validity",
        rule_version="1",
        epistemic_state=EpistemicState.MATCH,
        severity=Severity.INFO,
        title="SigningTime dentro do intervalo do certificado",
        statement=(
            "O SigningTime observado está dentro do intervalo NotBefore/NotAfter "
            "declarado pelo certificado associado."
        ),
        supporting_occurrence_ids=("signing", "not-before", "not-after"),
        metadata={"position": "inside", "delta_seconds": 0.0},
    )
    snapshot = CanonicalCasePipelineResult(
        report, CaseEvidenceIndex(report), CaseResult("case-1", findings=(finding,)),
    )

    model = build_correlation_explorer_model(snapshot)
    verification = model.verification_groups[0].items[0]

    assert verification.state == "MATCH"
    assert verification.details[0] == ("Distância do intervalo (segundos)", "0.0")
    assert "assinatura válida" not in (
        verification.title + verification.description
    ).casefold()


@pytest.mark.parametrize("tokens", [LIGHT_THEME, DARK_THEME])
def test_summary_and_explorer_render_in_both_themes(qt_app, tmp_path: Path, tokens) -> None:
    stylesheet = load_desktop_stylesheet(ApplicationPaths.discover(), tokens)
    qt_app.setStyleSheet(stylesheet)
    assert (
        f"QProgressBar#CorrelationCategoryBar::chunk {{ background: {tokens.text_muted};"
        in stylesheet
    )
    assert "CorrelationSummaryRow:focus QProgressBar" not in stylesheet
    results = [_result(tmp_path, "a.pdf", cpf="52998224725"),
               _result(tmp_path, "b.pdf", cpf="52998224725")]
    page = CorrelationExplorerPage(); page.update_case("case-1", results, _snapshot(results))
    page.resize(900, 640); page.show(); qt_app.processEvents()
    assert page.findChild(QProgressBar, "CorrelationCategoryBar").isVisibleTo(page)
    page.show_explorer(); qt_app.processEvents()
    assert page.list_scroll.isVisibleTo(page) and page.detail_scroll.isVisibleTo(page)
    page.close()
    qt_app.setStyleSheet(load_desktop_stylesheet(ApplicationPaths.discover(), LIGHT_THEME))


@pytest.mark.parametrize("point_size", [9, 12, 15])
def test_three_line_rows_follow_font_metrics_without_overlap(qt_app, point_size: int) -> None:
    page = CorrelationExplorerPage(); font = QFont(page.font()); font.setPointSize(point_size)
    page.setFont(font); element = _element_with_occurrences("cpf", "identifiers", ["a", "b"])
    page._case_id = "case-1"; page._model = CorrelationExplorerModel((element,))
    page._summary = build_case_correlation_summary(page._model, []); page._refresh_list()
    page.show_explorer(); page.resize(900, 500); page.show(); qt_app.processEvents()
    button = page._element_buttons["cpf"]
    children_bottom = max(label.geometry().bottom() for label in button.findChildren(QLabel))
    assert button.height() >= button.minimumSizeHint().height()
    assert children_bottom < button.height()
    page.close()


def test_narrow_explorer_stacks_without_page_horizontal_scroll(qt_app) -> None:
    page = CorrelationExplorerPage(); page.resize(700, 640); page.show(); qt_app.processEvents()
    assert page.splitter.orientation() == Qt.Orientation.Vertical
    assert page.summary_view.horizontalScrollBar().maximum() == 0
    page.resize(1200, 720); qt_app.processEvents()
    assert page.splitter.orientation() == Qt.Orientation.Horizontal
    page.close()


def test_summary_rebuilt_after_narrow_resize_keeps_stacked_metrics(qt_app, tmp_path: Path) -> None:
    results = [_result(tmp_path, "a.pdf", cpf="52998224725"),
               _result(tmp_path, "b.pdf", cpf="52998224725")]
    page = CorrelationExplorerPage(); page.resize(700, 640); page.show()
    qt_app.processEvents()

    page.update_case("case-1", results, _snapshot(results))
    qt_app.processEvents()

    assert page.summary_metric_layout is not None
    assert page.summary_metric_layout.direction() == QBoxLayout.Direction.TopToBottom
    assert page.explorer_controls_layout is not None
    assert page.explorer_controls_layout.direction() == QBoxLayout.Direction.TopToBottom
    page.close()


def test_large_occurrence_detail_is_visually_bounded_without_data_loss(qt_app) -> None:
    page = CorrelationExplorerPage()
    element = _element_with_occurrences(
        "many", "identifiers", ["artifact-a"] * 120,
    )

    page._render_detail(element)

    provenance = page.detail_content.findChildren(QLabel, "CorrelationProvenance")
    text = "\n".join(label.text() for label in page.detail_content.findChildren(QLabel))
    assert len(provenance) == page.MAX_VISIBLE_OCCURRENCES_PER_ARTIFACT
    assert "70 ocorrência(s) adicional(is)" in text
    assert element.occurrence_count == 120

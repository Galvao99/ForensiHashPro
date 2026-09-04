from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.entities.models import (
    EntitySource, EntitySourceType, EntityType as ResolvedEntityType, NormalizedEntity,
)
from app.investigation.declared_hash import DeclaredHashExtractor
from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
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


def _result(tmp_path: Path, name: str, *, cpf: str | None = None, digest: str = "a" * 64):
    entities = [_entity(cpf, name)] if cpf else []
    return SimpleNamespace(
        file_info=SimpleNamespace(name=name, path=tmp_path / name),
        hashes=SimpleNamespace(sha256=digest, md5=digest[:32]),
        metadata=SimpleNamespace(raw={}), resolved_entities=entities,
        processing_steps=(), extracted_text="", json_analysis=None,
        timeline_events=(), evidence_source=None,
    )


def test_same_identifier_is_observation_not_same_document(tmp_path: Path) -> None:
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
        _result(tmp_path, "b.pdf", cpf="52998224725"),
    ], context=InvestigationContext())
    cpf = next(item for item in model.elements if item.type_label == "CPF")
    assert cpf.artifact_count == 2
    assert cpf.relation_label == "Mesmo valor normalizado observado"
    assert cpf.deterministic_state is None
    assert "documento" not in cpf.relation_label.casefold()


def test_counts_provenance_and_frequency_are_descriptive(tmp_path: Path) -> None:
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
        _result(tmp_path, "b.pdf", cpf="52998224725"),
    ], context=InvestigationContext())
    cpf = next(item for item in model.elements if item.type_label == "CPF")
    assert (cpf.artifact_count, cpf.occurrence_count) == (2, 2)
    assert cpf.occurrences[0].page == 1
    assert "Página 1" in cpf.occurrences[0].provenance_label
    ordered = filter_correlation_elements(model.elements, sort_by="occurrences")
    assert {item.deterministic_state for item in ordered if item.type_label == "CPF"} == {None}


def test_calculated_hash_match_is_deterministic_and_source_typed(tmp_path: Path) -> None:
    digest = "d" * 64
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.bin", digest=digest),
        _result(tmp_path, "b.bin", digest=digest),
    ], context=InvestigationContext())
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
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.pdf"), _result(tmp_path, "b.pdf"),
    ], context=context)
    observed = [item for item in model.elements if "compatível" in item.type_label or "declarado" in item.type_label]
    assert {item.occurrences[0].source_kind for item in observed} == {"declared_hash", "hash_like"}
    assert all(item.deterministic_state is None for item in observed)


def test_producer_distribution_is_neutral(tmp_path: Path) -> None:
    context = InvestigationContext(
        producers={"a.pdf": "Adobe Acrobat", "b.pdf": "LibreOffice"},
        creators={"a.pdf": "Editor X"},
    )
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.pdf"), _result(tmp_path, "b.pdf"),
    ], context=context)
    producers = [item for item in model.elements if item.type_label == "Produtor"]
    assert len(producers) == 2
    assert all(item.deterministic_state is None for item in producers)
    assert all("alert" not in item.relation_label.casefold() for item in producers)


def test_search_normalizes_spacing_and_does_not_mutate_model(tmp_path: Path) -> None:
    model = build_correlation_explorer_model([
        _result(tmp_path, "a.pdf", cpf="52998224725"),
    ], context=InvestigationContext())
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
    page.update_case([result], context=InvestigationContext())
    page.update_case([result], context=InvestigationContext())
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
    page._summary = build_case_correlation_summary(page._model, [], None)
    page._refresh_list()
    page.show_explorer()
    page.show()
    qt_app.processEvents()
    assert page.list_scroll.verticalScrollBar().maximum() > 0
    assert page.splitter.sizes()[0] < page.splitter.sizes()[1]
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
        CorrelationExplorerModel((element,)), [_result(tmp_path, "a.pdf")], None,
    )
    assert summary.correlated_element_count == 0
    assert not summary.correlated_element_ids


def test_repeated_occurrences_in_same_artifact_are_not_cross_artifact(tmp_path: Path) -> None:
    element = _element_with_occurrences("repeat", "other", ["a"] * 84)
    summary = build_case_correlation_summary(
        CorrelationExplorerModel((element,)), [_result(tmp_path, "a.pdf")], None,
    )
    assert element.occurrence_count == 84
    assert element.artifact_count == 1
    assert summary.correlated_element_count == 0
    assert summary.categories == ()


@pytest.mark.parametrize("artifact_ids", [["a", "b"], ["a", "b", "c", "d", "e"]])
def test_same_value_across_distinct_artifacts_counts_once(tmp_path: Path, artifact_ids: list[str]) -> None:
    element = _element_with_occurrences("cpf-x", "identifiers", artifact_ids)
    results = [_result(tmp_path, f"{artifact_id}.pdf") for artifact_id in artifact_ids]
    summary = build_case_correlation_summary(CorrelationExplorerModel((element,)), results, None)
    assert summary.correlated_element_count == 1
    assert summary.participating_artifact_count == len(artifact_ids)
    assert summary.categories[0].element_count == 1


def test_category_summary_counts_elements_not_occurrences(tmp_path: Path) -> None:
    cpf = _element_with_occurrences("cpf", "identifiers", ["a", "b", "b"])
    temporal = _element_with_occurrences("date", "temporal", ["a", "b", "a", "b"])
    noise = _element_with_occurrences("money", "other", ["a"] * 50)
    summary = build_case_correlation_summary(
        CorrelationExplorerModel((cpf, temporal, noise)),
        [_result(tmp_path, "a.pdf"), _result(tmp_path, "b.pdf"), _result(tmp_path, "c.pdf")], None,
    )
    assert summary.correlated_element_count == 2
    assert [(item.label, item.element_count) for item in summary.categories] == [
        ("Identificadores e identidades", 1), ("Temporal", 1),
    ]
    assert summary.artifact_without_relation_count == 1


def test_only_canonical_findings_create_cross_source_verifications(tmp_path: Path) -> None:
    finding = CorrelationFinding(
        title="Comparação cronológica de datas declaradas", description="Relação técnica.",
        rule_id="metadata_contract_date", category="correlation", source_file="a.pdf",
        metadata={
            "data_pactuacao": "2021-03-05T00:00:00",
            "data_criacao_metadados": "2021-03-05T10:00:00",
            "diferenca_dias": 0,
        },
    )
    summary = build_case_correlation_summary(
        CorrelationExplorerModel(()), [_result(tmp_path, "a.pdf")], CorrelationResult([finding]),
    )
    group = summary.verification_groups[0]
    assert group.label == "Data documental × Metadados"
    assert group.items[0].state == "CONVERGENTE"


def test_different_dates_without_applicable_rule_never_become_divergent(tmp_path: Path) -> None:
    summary = build_case_correlation_summary(
        CorrelationExplorerModel(()), [_result(tmp_path, "a.pdf")], CorrelationResult(),
    )
    assert summary.verification_groups == ()


def test_hash_verification_states_come_from_existing_rule_categories(tmp_path: Path) -> None:
    result = CorrelationResult([
        CorrelationFinding(
            "Hash declarado correspondente", "Correspondência exata.", rule_id="embedded_hash_match",
            category="embedded_hash_match", metadata={"algorithm": "SHA-256", "hash": "a" * 64},
        ),
        CorrelationFinding(
            "Hash declarado sem correspondência", "Sem alvo no conjunto.",
            rule_id="embedded_hash_unmatched", category="embedded_hash_unmatched",
            metadata={"algorithm": "SHA-256", "hash": "b" * 64},
        ),
    ])
    summary = build_case_correlation_summary(
        CorrelationExplorerModel(()), [_result(tmp_path, "a.pdf")], result,
    )
    group = summary.verification_groups[0]
    assert [item.state for item in group.items] == ["CONVERGENTE", "INDETERMINADA"]


def test_summary_explorer_back_preserves_state_without_rebuilding(qt_app) -> None:
    page = CorrelationExplorerPage()
    element = _element_with_occurrences("cpf", "identifiers", ["a", "b"])
    page._model = CorrelationExplorerModel((element,))
    page._summary = build_case_correlation_summary(page._model, [], None)
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
    assert "artefatos analisados" in text
    assert "Ver todas as correlações" in buttons

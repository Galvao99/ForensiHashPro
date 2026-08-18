from __future__ import annotations

import base64
from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QApplication

from app.deep_structure.models import StructureReport
from app.pages.deep_file_explorer_page import DeepFileExplorerPage, ObjectInspector, _display_payload
from app.widgets.deep_file_explorer.tree_model import StructureTreeModel


PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _payload() -> dict:
    summary = {
        "object_count": 9, "page_count": 1, "stream_count": 4, "image_count": 2,
        "font_count": 1, "annotation_count": 1, "embedded_file_count": 1,
        "signature_dictionary_count": 1, "revision_count": 1, "unique_image_objects": 2,
        "image_references": 3, "unique_font_objects": 1, "font_references": 1,
        "pages_with_annotations": 1, "unique_annotation_objects": 1,
        "annotation_references": 1, "visual_resource_references": 3,
        "invoked_xobject_usages": 2,
    }
    physical = {
        "file_size": 100, "magic_bytes_hex": "25504446", "pdf_version": "1.7",
        "header_offset": 0, "eof_count": 1, "eof_offsets": [90],
        "startxref_offsets": [80], "bytes_after_last_eof": 0,
    }
    objects = []
    for number, kind, subtype, stream in [
        (1, "Catalog", None, False), (2, "Pages", None, False), (3, "Page", None, False),
        (4, "Stream", None, True), (7, "XObject", "Image", True),
        (8, "XObject", "Form", True), (9, "XObject", "Image", True),
        (10, "Metadata", "XML", True), (11, "Annot", "Text", False),
    ]:
        objects.append({
            "id": f"{number}_0", "object_number": number, "generation_number": 0,
            "object_type": kind, "subtype": subtype, "offset": number * 10,
            "raw_length": 10, "is_stream": stream,
            "dictionary": {"/Type": {"kind": "name", "value": f"/{kind}"}}, "references": [],
        })
    return {
        "format": "PDF", "contract_version": "1.2", "parser": "test", "physical": physical,
        "summary": summary, "objects": objects, "references": [
            {"source": "3_0", "target": "2_0", "path": "/Parent", "relationship": "Parent"},
            {"source": "2_0", "target": "3_0", "path": "/Kids[0]", "relationship": "Kids"},
        ], "xref": [], "trailer": {}, "catalog": {"object_id": "1_0", "pages": "2_0"},
        "page_tree": {"effective_count": 1, "pages": [{
            "page_number": 1, "object_id": "3_0", "parent": "2_0", "media_box": None,
            "crop_box": None, "rotate": 0, "resources": "inline", "contents": "4_0",
            "content_object_ids": ["4_0"], "annots": "11_0",
        }]},
        "resources": [], "streams": [], "images": [{
            "object_id": "7_0", "width": 1, "height": 1, "bits_per_component": 8,
            "color_space": "/DeviceRGB", "filters": ["/FlateDecode"], "raw_size": 3,
            "decoded_size": 3, "mask": None, "soft_mask": "9_0",
        }], "embedded_items": [],
        "previewable_assets": [
            {"id": "pdf_object_7_0", "kind": "image", "object_id": "7_0", "media_type": "image/png",
             "previewable": True, "direct_preview": False, "preview_available": True},
            {"id": "pdf_object_9_0", "kind": "image", "object_id": "9_0", "media_type": "image/png",
             "previewable": True, "direct_preview": False, "preview_available": True},
        ],
        "visual_resources": [
            {"page_object_id": "3_0", "container_object_id": "3_0", "resource_name": "Im1",
             "object_id": "7_0", "kind": "image", "path": "/Resources/XObject/Im1", "depth": 0,
             "declared": True, "invoked_by_do": True},
            {"page_object_id": "3_0", "container_object_id": "3_0", "resource_name": "Fm1",
             "object_id": "8_0", "kind": "form", "path": "/Resources/XObject/Fm1", "depth": 0,
             "declared": True, "invoked_by_do": True},
            {"page_object_id": "3_0", "container_object_id": "8_0", "resource_name": "Im2",
             "object_id": "9_0", "kind": "image", "path": "/Resources/XObject/Fm1/Resources/XObject/Im2",
             "depth": 1, "declared": True, "invoked_by_do": False},
        ],
        "forms": [{"object_id": "8_0", "bbox": [0, 0, 10, 10], "matrix": None,
                   "resources": {}, "group": None, "content_available": True}],
        "embedded_files": [{"id": "embedded_12_0", "filename": "note.txt", "unicode_filename": "nota.txt",
                            "mime_type": "text/plain", "size": 7, "object_id": "12_0",
                            "stream_available": True, "warnings": []}],
        "metadata_streams": [{"object_id": "10_0", "subtype": "XML", "raw_available": True,
                              "decoded_available": True}],
        "annotations": [{"object_id": "11_0", "page_object_ids": ["3_0"], "subtype": "Text",
                         "properties": {"/Contents": {"kind": "string", "value": "nota"}}}],
        "signatures": [{"object_id": "13_0", "properties": {"/SubFilter": {"kind": "name", "value": "/adbe.pkcs7.detached"}}}],
        "occurrences": [{"name": "/FlateDecode", "count": 2}], "parser_warnings": [],
    }


class FakeSession:
    def __init__(self) -> None:
        self.report = StructureReport.from_dict(_payload())
        self.calls: list[tuple[str, str]] = []

    def get_object(self, object_id): self.calls.append(("object", object_id)); return {"id": object_id, "dictionary": {}}
    def get_raw_object(self, object_id): self.calls.append(("raw", object_id)); return b"7 0 obj\nendobj"
    def get_decoded_stream(self, object_id): self.calls.append(("decoded", object_id)); return b"q /Im1 Do Q"
    def get_preview(self, object_id): self.calls.append(("preview", object_id)); return PNG
    def get_visual_asset(self, object_id):
        return {"source_object_id": object_id, "reconstructed": True,
                "provenance": {"source_filter": "FlateDecode", "transformation": "decoded_pixels_to_png"}}
    def get_embedded_file(self, object_id): self.calls.append(("embedded", object_id)); return b"payload"
    def get_metadata_text(self, object_id): self.calls.append(("metadata", object_id)); return "<x:xmpmeta/>"


def _walk(model: StructureTreeModel, parent=QModelIndex()):
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        yield index, model.node_from_index(index)
        yield from _walk(model, index)


def test_tree_builds_page_resource_form_and_content_relationships() -> None:
    model = StructureTreeModel(StructureReport.from_dict(_payload()))
    labels = [node.label for _, node in _walk(model)]
    assert any("Page 1 [3 0 R]" in label for label in labels)
    assert any("/Im1 → 7 0 R  [invoked]" in label for label in labels)
    assert any("/Im2 → 9 0 R  [declared]" in label for label in labels)
    assert any("Content Stream [4 0 R]" in label for label in labels)
    assert any("SMask [9 0 R]" in label for label in labels)
    nested = next(node for _, node in _walk(model) if "/Im2 → 9 0 R" in node.label)
    assert nested.parent is not None and nested.parent.parent is not None
    assert "/Fm1 → 8 0 R" in nested.parent.parent.label


def test_objects_are_loaded_lazily_and_keep_generation_identity() -> None:
    model = StructureTreeModel(StructureReport.from_dict(_payload()))
    objects_index = next(index for index, node in _walk(model) if node.kind == "objects")
    assert model.rowCount(objects_index) == 0
    assert model.canFetchMore(objects_index)
    model.fetchMore(objects_index)
    assert model.rowCount(objects_index) == 9
    assert "7 0 R" in model.data(model.index(4, 0, objects_index))


def test_cyclic_edges_do_not_expand_the_tree() -> None:
    model = StructureTreeModel(StructureReport.from_dict(_payload()))
    assert sum(1 for _ in _walk(model)) < 40


def test_collections_expose_metadata_annotation_signature_and_embedded() -> None:
    model = StructureTreeModel(StructureReport.from_dict(_payload()))
    kinds = {node.kind for _, node in _walk(model)}
    assert {"metadata", "annotation", "signature", "embedded"} <= kinds


def test_inspector_loads_preview_decoded_raw_and_metadata_lazily(qt_app) -> None:
    session = FakeSession()
    inspector = ObjectInspector(lambda operation, success, failure: success(operation()))
    inspector.set_session(session)
    image = SimpleNamespace(object_id="7_0", kind="resource_image", payload={})
    inspector.select_node(image)
    assert ("preview", "7_0") in session.calls
    inspector.setCurrentIndex(2)
    assert ("decoded", "7_0") in session.calls
    inspector.setCurrentIndex(3)
    assert ("raw", "7_0") in session.calls
    metadata = SimpleNamespace(object_id="10_0", kind="metadata", payload={})
    inspector.setCurrentIndex(1)
    inspector.select_node(metadata)
    inspector.setCurrentIndex(2)
    assert "x:xmpmeta" in inspector.decoded.toPlainText()


def test_binary_payload_uses_bounded_hex_representation() -> None:
    text = _display_payload(bytes(range(256)))
    assert "Stream binário" in text
    assert "00000000" in text


def test_page_handles_non_pdf_without_parsing(qt_app, tmp_path: Path) -> None:
    engine = SimpleNamespace(analyze_pdf=lambda _path: pytest.fail("must not parse"))
    page = DeepFileExplorerPage(engine=engine)
    result = SimpleNamespace(file_info=SimpleNamespace(path=tmp_path / "a.txt", name="a.txt", size_bytes=1),
                             hashes=SimpleNamespace(sha256="abc"))
    page.update_analysis(result)
    assert "suporta PDF" in page.status_label.text()


@pytest.mark.parametrize("category", ["malformed", "limit_exceeded"])
def test_page_maps_technical_engine_errors(qt_app, category: str) -> None:
    page = DeepFileExplorerPage(engine=SimpleNamespace())
    page._structure_failed(category, "technical detail")
    assert category in page.status_label.text()
    assert "technical detail" in page.status_label.text()


def test_page_accepts_real_engine_session(qt_app, tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    from app.deep_structure import DeepFileStructureEngine

    path = tmp_path / "ui-real.pdf"
    document = fitz.open()
    document.new_page().insert_text((20, 20), "Deep Explorer")
    document.save(path)
    document.close()
    session = DeepFileStructureEngine().analyze_pdf(path)
    page = DeepFileExplorerPage()
    page._result = SimpleNamespace(file_info=SimpleNamespace(path=path))
    page._structure_loaded(session)
    assert page.tree_model.page_index(1).isValid()
    assert "Páginas 1" in page.summary.text()

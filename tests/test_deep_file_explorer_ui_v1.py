from types import SimpleNamespace

import pytest
from PySide6.QtCore import QModelIndex
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QTreeWidget

from app.deep_structure.models import JpegStructureReport
from app.pages.deep_file_explorer_page import ObjectInspector, _append_property_items
from app.widgets.deep_file_explorer.hex_viewer import HexViewerWidget
from app.widgets.deep_file_explorer.tree_model import StructureTreeModel


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _segment(index: int, marker: int, name: str, *, metadata=None) -> dict:
    offset = index * 20
    return {"index": index, "marker": marker, "marker_hex": f"FF{marker:02X}", "marker_name": name,
            "offset": offset, "marker_offset": offset, "payload_offset": offset + 4,
            "declared_length": 18, "payload_length": 16, "end_offset": offset + 20,
            "category": "application" if name.startswith("APP") else "coding", "summary": name,
            "metadata": metadata}


def jpeg_report() -> JpegStructureReport:
    segments = [
        _segment(0, 0xD8, "SOI"),
        _segment(1, 0xE0, "APP0", metadata={"identifier": "JFIF"}),
        _segment(2, 0xE1, "APP1", metadata={"kind": "exif"}),
        _segment(3, 0xE1, "APP1", metadata={"kind": "xmp", "id": "xmp_3"}),
        _segment(4, 0xE2, "APP2", metadata={"kind": "icc_profile"}),
        _segment(5, 0xDB, "DQT"), _segment(6, 0xC2, "SOF2"),
        _segment(7, 0xDA, "SOS"), _segment(8, 0xD9, "EOI"),
    ]
    return JpegStructureReport.from_dict({
        "format": "jpeg", "structure_version": "1.0", "parser": "test",
        "physical_info": {"file_size": 2048, "soi_offset": 0, "eoi_offset": 180,
                          "trailing_bytes_offset": 182, "trailing_bytes_length": 12,
                          "segment_count": len(segments), "scan_count": 2},
        "segments": segments,
        "scans": [{"index": 0, "sos_segment_index": 7, "data_offset": 150, "data_length": 20,
                   "restart_markers": [], "end_offset": 170},
                  {"index": 1, "sos_segment_index": 7, "data_offset": 170, "data_length": 10,
                   "restart_markers": [], "end_offset": 180}],
        "frames": [{"segment_index": 6, "frame_type": "progressive_dct", "width": 4000,
                    "height": 3000, "precision": 8, "number_of_components": 3}],
        "quantization_tables": [{"segment_index": 5, "table_id": 0, "precision_bits": 8, "values": [1] * 64}],
        "huffman_tables": [{"segment_index": 7, "table_id": 0, "class": "dc", "counts": [0] * 16,
                            "symbols": [], "symbol_count": 0}],
        "exif": [{"segment_index": 2, "byte_order": "little_endian", "tiff_offset": 44, "ifds": [
            {"id": "IFD0", "kind": "IFD0", "offset_relative_to_tiff": 8, "absolute_offset": 52,
             "next_ifd_offset": 0, "entries": [
                {"tag_id": 0x8769, "tag_name": "ExifIFDPointer", "value_type": 4, "count": 1,
                 "value_or_offset": 40, "decoded_value": [40], "raw_value_location": 62,
                 "path": "IFD0/0x8769"}]},
            {"id": "ExifIFD", "kind": "ExifIFD", "offset_relative_to_tiff": 40, "absolute_offset": 84,
             "next_ifd_offset": 0, "entries": [
                {"tag_id": 0x9003, "tag_name": "DateTimeOriginal", "value_type": 2, "count": 20,
                 "value_or_offset": 80, "decoded_value": "2024:08:13 15:18:48",
                 "raw_value_location": 124, "path": "ExifIFD/0x9003"}]},
        ]}],
        "xmp": [{"id": "xmp_3", "segment_index": 3, "offset": 80, "length": 20,
                 "kind": "standard", "utf8_valid": True}],
        "icc": [{"sequence_number": 1, "total_chunks": 1, "segment_index": 4, "offset": 104, "length": 24}],
        "visual_assets": [{"id": "jpeg_main", "kind": "main_image", "media_type": "image/jpeg",
                           "offset": 0, "length": 2048, "preview_available": True,
                           "provenance": "original_file_bytes"},
                          {"id": "exif_thumbnail_2", "kind": "exif_thumbnail", "media_type": "image/jpeg",
                           "offset": 130, "length": 16, "preview_available": True,
                           "provenance": "segment:2:APP1/EXIF/IFD1"}],
        "comments": [{"segment_index": 5, "offset": 120, "length": 7, "text": "comment"}],
        "warnings": [{"code": "trailing_bytes", "message": "12 bytes after EOI", "offset": 182}],
        "capabilities": {"segment_raw": True, "scan_raw": True, "exif_navigation": True,
                         "xmp_text": True, "icc_reconstruction": True, "lazy_visual_assets": True},
    })


def _walk(model, parent=QModelIndex()):
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent); node = model.node_from_index(index)
        yield index, node
        yield from _walk(model, index)


def test_jpeg_tree_exposes_segments_exif_assets_scans_and_warnings() -> None:
    model = StructureTreeModel(jpeg_report())
    nodes = [node for _, node in _walk(model)]
    labels = {node.label for node in nodes}
    assert {"JPEG", "Physical Structure", "APP1 / EXIF #0"} <= labels
    assert any("#1 APP0 — JFIF" == label for label in labels)
    assert any(node.kind == "jpeg_exif_entry" and node.label == "DateTimeOriginal" for node in nodes)
    assert any(node.kind == "jpeg_scan" and "raw" in node.capabilities for node in nodes)
    assert any(node.kind == "jpeg_asset" and node.preview_asset_id == "exif_thumbnail_2" for node in nodes)
    assert any(node.kind == "jpeg_warning" for node in nodes)


class JpegSession:
    def __init__(self): self.calls = []
    def get_segment_raw(self, index): self.calls.append(("segment", index)); return b"\xff\xe1Exif\0\0"
    def get_scan_raw(self, index): self.calls.append(("scan", index)); return b"\x01\xff\x00\x02"
    def get_xmp_raw(self, packet): self.calls.append(("xmp_raw", packet)); return b"<xmp/>"
    def get_xmp_text(self, packet): self.calls.append(("xmp_text", packet)); return "<xmp/>"
    def get_icc_profile(self): self.calls.append(("icc", "profile")); return b"ICC"
    def get_trailing_bytes(self): self.calls.append(("trailing", "bytes")); return b"tail"
    def get_visual_asset(self, asset): self.calls.append(("asset", asset)); return b"jpeg"
    def get_preview(self, asset): self.calls.append(("preview", asset)); return b"jpeg"


def test_jpeg_inspector_raw_scan_xmp_icc_trailing_and_exif_are_lazy(qt_app) -> None:
    model = StructureTreeModel(jpeg_report()); session = JpegSession()
    inspector = ObjectInspector(lambda operation, success, failure: success(operation()))
    inspector.set_session(session)
    nodes = [node for _, node in _walk(model)]
    segment = next(node for node in nodes if node.kind == "jpeg_segment" and node.segment_index == 2)
    inspector.select_node(segment); inspector.setCurrentIndex(3); assert ("segment", 2) in session.calls
    inspector.setCurrentIndex(5); assert "FF E1" in inspector.hex_viewer.viewer.toPlainText()
    scan = next(node for node in nodes if node.kind == "jpeg_scan")
    inspector.select_node(scan); inspector.setCurrentIndex(3); assert any(call[0] == "scan" for call in session.calls)
    xmp = next(node for node in nodes if node.kind == "jpeg_xmp")
    inspector.select_node(xmp); inspector.setCurrentIndex(4); assert inspector.text.toPlainText() == "<xmp/>"
    trailing = next(node for node in nodes if node.kind == "jpeg_trailing")
    inspector.select_node(trailing); inspector.setCurrentIndex(3); assert inspector.raw.toPlainText() == "tail"
    entry = next(node for node in nodes if node.kind == "jpeg_exif_entry" and node.label == "DateTimeOriginal")
    inspector.select_node(entry); inspector.setCurrentIndex(2)
    assert "2024:08:13" in inspector.decoded.toPlainText()
    assert "0x9003" in str(inspector._summary_payload(entry).values())


def test_hex_viewer_is_bounded_and_can_load_more(qt_app) -> None:
    viewer = HexViewerWidget(initial_limit=16, maximum_limit=32)
    viewer.set_bytes(bytes(range(64)))
    assert "00000000" in viewer.viewer.toPlainText()
    assert "16 de 64" in viewer.status.text() and not viewer.load_more_button.isHidden()
    viewer.load_more()
    assert "32 de 64" in viewer.status.text()
    assert not viewer.load_more_button.isVisible()


def test_exif_pointer_has_stable_cross_navigation_target() -> None:
    model = StructureTreeModel(jpeg_report())
    pointer = next(node for _, node in _walk(model) if node.kind == "jpeg_exif_entry" and node.label == "ExifIFDPointer")
    target = pointer.payload["structural_target_id"]
    assert model.index_for_node_id(target).isValid()


def test_stale_inspector_callback_does_not_replace_new_selection(qt_app) -> None:
    pending = []
    inspector = ObjectInspector(lambda operation, success, failure: pending.append((operation, success, failure)))
    inspector.set_session(JpegSession())
    model = StructureTreeModel(jpeg_report()); nodes = [node for _, node in _walk(model)]
    segment = next(node for node in nodes if node.kind == "jpeg_segment")
    scan = next(node for node in nodes if node.kind == "jpeg_scan")
    inspector.select_node(segment); inspector.setCurrentIndex(3)
    old_operation, old_success, _ = pending[-1]
    inspector.select_node(scan)
    old_success(old_operation())
    assert "FF E1" not in inspector.raw.toPlainText()


def test_typed_pdf_reference_is_legible_and_clickable(qt_app) -> None:
    tree = QTreeWidget(); root = tree.invisibleRootItem()
    _append_property_items(root, {"/Target": {"kind": "reference", "reference": "15_0",
                                                        "value": "15 0 R", "items": [], "entries": {}}})
    item = root.child(0)
    assert item.text(1) == "reference"
    assert "15 0 R" in item.text(2)
    assert item.data(0, Qt.UserRole) == "15_0"

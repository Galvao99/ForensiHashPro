import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.deep_structure import DeepFileStructureEngine, DeepStructureError


def report_payload() -> dict:
    return {
        "format": "PDF", "contract_version": "1.2", "parser": "lopdf+bounded_physical_scan",
        "physical": {"file_size": 12, "magic_bytes_hex": "25 50 44 46", "pdf_version": "1.7", "header_offset": 0,
                     "eof_count": 1, "eof_offsets": [7], "startxref_offsets": [3], "bytes_after_last_eof": 0},
        "summary": {"object_count": 1, "page_count": 1, "stream_count": 1, "image_count": 1, "font_count": 0,
                    "annotation_count": 0, "embedded_file_count": 0, "signature_dictionary_count": 0, "revision_count": 1,
                    "unique_image_objects": 1, "image_references": 1, "unique_font_objects": 0, "font_references": 0,
                    "pages_with_annotations": 0, "unique_annotation_objects": 0, "annotation_references": 0,
                    "visual_resource_references": 1, "invoked_xobject_usages": 1},
        "objects": [{"id": "7_0", "object_number": 7, "generation_number": 0, "object_type": "XObject",
                     "subtype": "Image", "offset": 10, "raw_length": 20, "is_stream": True,
                     "dictionary": {"/Subtype": {"kind": "name", "value": "/Image", "reference": None, "items": [], "entries": {}}}, "references": []}],
        "references": [], "xref": [], "trailer": {}, "catalog": {}, "page_tree": {"effective_count": 1},
        "resources": [], "streams": [], "images": [], "embedded_items": [],
        "previewable_assets": [{"id": "pdf_object_7_0", "kind": "image", "object_id": "7_0", "media_type": "image/jpeg",
                                "previewable": True, "direct_preview": True, "preview_available": True}],
        "visual_resources": [], "forms": [], "embedded_files": [], "metadata_streams": [], "annotations": [], "signatures": [],
        "occurrences": [{"name": "/Image", "count": 1}], "parser_warnings": [],
    }


class NativeSession:
    def report_json(self) -> str: return json.dumps(report_payload())
    def get_object(self, object_id: str) -> str: return json.dumps({"id": object_id})
    def get_raw_object(self, object_id: str) -> bytes: return b"raw-object"
    def get_raw_stream(self, object_id: str) -> bytes: return b"raw"
    def get_decoded_stream(self, object_id: str) -> bytes: return b"decoded"
    def get_preview(self, object_id: str) -> bytes: return b"jpeg"
    def get_visual_asset(self, object_id: str) -> str: return json.dumps({"source_object_id": object_id, "status": "direct"})
    def get_composite_preview(self, object_id: str) -> bytes: return b"png"
    def get_embedded_file(self, object_id: str) -> bytes: return b"embedded"
    def get_metadata_text(self, object_id: str) -> str: return "<xmp/>"


def test_typed_report_and_on_demand_access(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = []
    core = SimpleNamespace(analyze_pdf=lambda *args: calls.append(args) or NativeSession())
    monkeypatch.setitem(sys.modules, "forensihash_core", core)
    path = tmp_path / "sample.pdf"
    path.write_bytes(b"%PDF-1.7")
    session = DeepFileStructureEngine(max_file_bytes=100, max_decoded_stream_bytes=50).analyze_pdf(path)
    assert session.report.summary.image_count == 1
    assert session.report.objects[0].subtype == "Image"
    assert session.get_object("7_0") == {"id": "7_0"}
    assert session.get_raw_object("7_0") == b"raw-object"
    assert session.get_raw_stream("7_0") == b"raw"
    assert session.get_decoded_stream("7_0") == b"decoded"
    assert session.get_preview("7_0") == b"jpeg"
    assert session.get_visual_asset("7_0")["status"] == "direct"
    assert session.get_composite_preview("7_0") == b"png"
    assert session.get_embedded_file("7_0") == b"embedded"
    assert session.get_metadata_text("7_0") == "<xmp/>"
    assert calls[0][:3] == (str(path), 100, 50)
    assert len(calls[0]) == 9


@pytest.mark.parametrize("file_limit,stream_limit", [(0, 1), (1, 0), (-1, 1)])
def test_limits_must_be_positive(file_limit: int, stream_limit: int) -> None:
    with pytest.raises(ValueError):
        DeepFileStructureEngine(max_file_bytes=file_limit, max_decoded_stream_bytes=stream_limit)


def test_native_errors_receive_technical_category(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail(*_args):
        raise RuntimeError("Unable to parse PDF structure: invalid xref")

    monkeypatch.setitem(sys.modules, "forensihash_core", SimpleNamespace(analyze_pdf=fail))
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"%PDF-1.7")
    with pytest.raises(DeepStructureError) as captured:
        DeepFileStructureEngine().analyze_pdf(path)
    assert captured.value.category == "malformed"


def test_real_native_pdf_roundtrip(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    image_module = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "pixel.jpg"
    image_module.new("RGB", (2, 3), (255, 0, 0)).save(image_path, format="JPEG")
    pdf_path = tmp_path / "native.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_text((20, 20), "ForensiHash")
    page.insert_image(fitz.Rect(20, 30, 40, 60), filename=str(image_path))
    document.new_page()
    document.save(pdf_path)
    document.close()

    session = DeepFileStructureEngine().analyze_pdf(pdf_path)
    assert session.report.summary.page_count == 2
    assert session.report.summary.image_count >= 1
    asset = next(item for item in session.report.previewable_assets if item["kind"] == "image")
    usage = next(item for item in session.report.visual_resources if item["object_id"] == asset["object_id"])
    assert usage["declared"] is True
    assert usage["invoked_by_do"] is True
    assert asset["direct_preview"] is True
    properties = session.get_object(asset["object_id"])
    assert properties["id"] == asset["object_id"]
    assert properties["dictionary"]["/Width"]["kind"] == "integer"
    assert session.get_raw_object(asset["object_id"])
    assert session.get_raw_stream(asset["object_id"])
    preview = session.get_preview(asset["object_id"])
    assert preview == image_path.read_bytes()


def test_real_jpeg2000_preview_is_preserved_when_openjpeg_is_available(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    image_module = pytest.importorskip("PIL.Image")
    features = pytest.importorskip("PIL.features")
    if not features.check("jpg_2000"):
        pytest.skip("Pillow/OpenJPEG is unavailable")
    image_path = tmp_path / "pixel.jp2"
    image_module.new("RGB", (8, 8), (10, 20, 30)).save(image_path, format="JPEG2000")
    source_bytes = image_path.read_bytes()
    pdf_path = tmp_path / "jpx.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_image(fitz.Rect(0, 0, 8, 8), filename=str(image_path))
    document.save(pdf_path)
    document.close()

    session = DeepFileStructureEngine().analyze_pdf(pdf_path)
    image = next(item for item in session.report.images if "/JPXDecode" in item["filters"])
    asset = session.get_visual_asset(image["object_id"])
    assert asset["status"] == "direct"
    assert asset["mime_type"] == "image/jp2"
    assert session.get_preview(image["object_id"]) == source_bytes


def test_real_flate_iccbased_image_is_not_rendered_as_device_rgb(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    image_module = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "pixels.png"
    image_module.new("RGB", (16, 16), (40, 80, 120)).save(image_path, format="PNG")
    pdf_path = tmp_path / "flate.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_image(fitz.Rect(0, 0, 16, 16), filename=str(image_path))
    document.save(pdf_path, deflate=True)
    document.close()

    session = DeepFileStructureEngine().analyze_pdf(pdf_path)
    image = next(item for item in session.report.images if "/FlateDecode" in item["filters"])
    asset = session.get_visual_asset(image["object_id"])
    assert asset["color_space"] == "/ICCBased"
    assert asset["status"] == "unsupported"
    assert asset["preview_available"] is False


def test_real_flate_device_rgb_image_is_reconstructed_as_png(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    image_module = pytest.importorskip("PIL.Image")
    image_path = tmp_path / "device-rgb.png"
    image_module.new("RGB", (16, 16), (40, 80, 120)).save(image_path, format="PNG")
    pdf_path = tmp_path / "device-rgb.pdf"
    document = fitz.open()
    page = document.new_page()
    page.insert_image(fitz.Rect(0, 0, 16, 16), filename=str(image_path))
    image_xref = page.get_images(full=True)[0][0]
    document.xref_set_key(image_xref, "ColorSpace", "/DeviceRGB")
    document.save(pdf_path, deflate=True)
    document.close()

    session = DeepFileStructureEngine().analyze_pdf(pdf_path)
    image = next(item for item in session.report.images if "/FlateDecode" in item["filters"])
    asset = session.get_visual_asset(image["object_id"])
    assert asset["status"] == "reconstructed"
    assert asset["provenance"]["transformation"] == "decoded_pixels_to_png"
    assert session.get_preview(image["object_id"]).startswith(b"\x89PNG\r\n\x1a\n")


def test_real_embedded_metadata_and_annotation_access(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    fitz = pytest.importorskip("fitz")
    pdf_path = tmp_path / "content.pdf"
    document = fitz.open()
    page = document.new_page()
    page.add_text_annot((10, 10), "first")
    page.add_text_annot((20, 20), "second")
    document.embfile_add("note.txt", b"payload", filename="note.txt", ufilename="nota.txt")
    document.set_xml_metadata("<x:xmpmeta xmlns:x='adobe:ns:meta/'/>")
    document.save(pdf_path)
    document.close()

    session = DeepFileStructureEngine().analyze_pdf(pdf_path)
    assert session.report.summary.pages_with_annotations == 1
    assert session.report.summary.unique_annotation_objects == 4  # Text + Popup for each annotation
    assert session.report.summary.annotation_references == 4
    assert {item["subtype"] for item in session.report.annotations} == {"Text", "Popup"}
    embedded = session.report.embedded_files[0]
    assert embedded["filename"] == "note.txt"
    assert session.get_embedded_file(embedded["object_id"]) == b"payload"
    metadata = session.report.metadata_streams[0]
    assert "x:xmpmeta" in session.get_metadata_text(metadata["object_id"])

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtWidgets import QApplication

from app.deep_structure import DeepStructureError
from app.deep_structure.models import JpegStructureReport
from app.pages.deep_file_explorer_page import DeepFileExplorerPage


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def jpeg_report(*, progressive: bool = False, exif: bool = False, trailing: int = 0) -> JpegStructureReport:
    return JpegStructureReport.from_dict({
        "format": "jpeg", "structure_version": "1.0", "parser": "test",
        "physical_info": {"file_size": 100, "soi_offset": 0, "eoi_offset": 90,
                          "trailing_bytes_offset": 92 if trailing else None,
                          "trailing_bytes_length": int(trailing), "segment_count": 12,
                          "scan_count": 3 if progressive else 1},
        "segments": [], "scans": [],
        "frames": [{"width": 640, "height": 480,
                    "frame_type": "progressive_dct" if progressive else "baseline_dct"}],
        "quantization_tables": [], "huffman_tables": [],
        "exif": [{"ifds": []}] if exif else [], "xmp": [], "icc": [],
        "visual_assets": [], "comments": [], "warnings": [],
        "capabilities": {"segment_raw": True},
    })


class Session:
    def __init__(self, report): self.report = report


class RecorderEngine:
    def __init__(self, pdf_report=None) -> None:
        self.calls: list[tuple[str, Path]] = []
        self.pdf_report = pdf_report

    def analyze_jpeg(self, path: Path):
        self.calls.append(("jpeg", path)); return Session(jpeg_report(progressive="progressive" in path.name,
                                                                      exif="exif" in path.name,
                                                                      trailing="trailing" in path.name))

    def analyze_pdf(self, path: Path):
        self.calls.append(("pdf", path)); return Session(self.pdf_report)


def result(path: Path, detected_format: str | None):
    magic = SimpleNamespace(detected_format=detected_format) if detected_format is not None else None
    return SimpleNamespace(file_info=SimpleNamespace(path=path, name=path.name, size_bytes=10),
                           hashes=SimpleNamespace(sha256="abc"), magic_numbers=magic)


def make_page(engine) -> DeepFileExplorerPage:
    page = DeepFileExplorerPage(engine=engine)
    page.document_viewer.load = lambda _path: None
    page._submit = lambda operation, success, failure: _run(operation, success, failure)
    return page


def _run(operation, success, failure) -> None:
    try: success(operation())
    except Exception as error: failure(str(getattr(error, "category", "unavailable")), str(error))


@pytest.mark.parametrize("suffix", [".jpg", ".jpeg"])
def test_jpg_and_jpeg_route_to_jpeg_parser(qt_app, tmp_path: Path, suffix: str) -> None:
    engine = RecorderEngine(); page = make_page(engine); path = tmp_path / f"image{suffix}"
    page.update_analysis(result(path, "JPEG")); page.ensure_loaded()
    assert engine.calls == [("jpeg", path)]
    assert page._session.report.format == "jpeg"
    assert "JPEG Structural Report disponível" in page.status_label.text()


def test_magic_jpeg_wins_over_incorrect_extension(qt_app, tmp_path: Path) -> None:
    engine = RecorderEngine(); page = make_page(engine); path = tmp_path / "evidence.bin"
    page.update_analysis(result(path, "JPEG")); page.ensure_loaded()
    assert engine.calls == [("jpeg", path)]


@pytest.mark.parametrize("name,expected", [("baseline.jpg", "Scans 1"), ("progressive.jpg", "Scans 3"),
                                             ("exif.jpg", "EXIF sim"), ("trailing.jpg", "Trailing bytes 1")])
def test_jpeg_summary_variants(qt_app, tmp_path: Path, name: str, expected: str) -> None:
    page = make_page(RecorderEngine()); page.update_analysis(result(tmp_path / name, "JPEG")); page.ensure_loaded()
    assert expected in page.summary.text()
    assert page.tree_model.report.format == "jpeg"


def test_malformed_jpeg_is_controlled_and_does_not_keep_session(qt_app, tmp_path: Path) -> None:
    class Broken(RecorderEngine):
        def analyze_jpeg(self, path): raise DeepStructureError("malformed", "invalid segment")
    page = make_page(Broken()); page.update_analysis(result(tmp_path / "bad.jpg", "JPEG")); page.ensure_loaded()
    assert page._session is None
    assert "malformed" in page.status_label.text() and "invalid segment" in page.status_label.text()


def test_pdf_jpeg_pdf_routing_and_session_replacement(qt_app, tmp_path: Path) -> None:
    pdf_report = SimpleNamespace(format="PDF", physical=SimpleNamespace(pdf_version="1.7", eof_count=1,
        startxref_offsets=(),eof_offsets=(),bytes_after_last_eof=0),
        summary=SimpleNamespace(object_count=0,page_count=0,stream_count=0,unique_image_objects=0,image_references=0,
        unique_font_objects=0,unique_annotation_objects=0,embedded_file_count=0,signature_dictionary_count=0),
        forms=(),parser_warnings=(),objects=(),trailer={},catalog={},page_tree={},resources=(),annotations=(),
        visual_resources=(),images=(),previewable_assets=(),embedded_files=(),metadata_streams=(),signatures=(),occurrences=())
    engine=RecorderEngine(pdf_report);page=make_page(engine)
    paths=[tmp_path/"a.pdf",tmp_path/"b.jpg",tmp_path/"c.pdf"]
    sessions=[]
    for path,kind in zip(paths,["PDF","JPEG","PDF"]):
        page.update_analysis(result(path,kind));page.ensure_loaded();sessions.append(page._session)
    assert [call[0] for call in engine.calls]==["pdf","jpeg","pdf"]
    assert len({id(item) for item in sessions})==3


def test_jpeg_to_jpeg_discards_previous_session(qt_app, tmp_path: Path) -> None:
    page=make_page(RecorderEngine());page.update_analysis(result(tmp_path/"a.jpg","JPEG"));page.ensure_loaded();old=page._session
    page.update_analysis(result(tmp_path/"b.jpeg","JPEG"))
    assert page._session is None
    page.ensure_loaded();assert page._session is not old


def test_jpeg_to_png_and_home_release_session(qt_app, tmp_path: Path) -> None:
    engine=RecorderEngine();page=make_page(engine);page.update_analysis(result(tmp_path/"a.jpg","JPEG"));page.ensure_loaded()
    page.update_analysis(result(tmp_path/"a.png","PNG"));assert page._session is None
    page.update_analysis(result(tmp_path/"b.jpg","JPEG"));page.ensure_loaded();page.release_analysis()
    assert page._session is None and page._result is None


def test_extension_fallback_and_parser_separation(qt_app, tmp_path: Path) -> None:
    engine=RecorderEngine();page=make_page(engine)
    page.update_analysis(result(tmp_path/"fallback.jpeg",None));page.ensure_loaded()
    page.update_analysis(result(tmp_path/"document.pdf",None));page.ensure_loaded()
    assert [call[0] for call in engine.calls]==["jpeg","pdf"]


def test_stale_async_result_cannot_replace_current_file(qt_app, tmp_path: Path) -> None:
    page=make_page(RecorderEngine());old=tmp_path/"old.jpg";new=tmp_path/"new.jpg"
    page.update_analysis(result(old,"JPEG"));page.update_analysis(result(new,"JPEG"))
    stale=Session(jpeg_report());page._structure_loaded_for(old,stale)
    assert page._session is None

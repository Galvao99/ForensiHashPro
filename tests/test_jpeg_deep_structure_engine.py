import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.deep_structure import DeepFileStructureEngine, DeepStructureError


def _report() -> dict:
    return {
        "format": "jpeg", "structure_version": "1.0", "parser": "forensihash-jpeg-structural-v1",
        "physical_info": {"file_size": 8, "soi_offset": 0, "eoi_offset": 4,
                          "trailing_bytes_offset": 6, "trailing_bytes_length": 2,
                          "segment_count": 2, "scan_count": 0},
        "segments": [{"index": 0, "marker": 216, "marker_hex": "FFD8", "marker_name": "SOI",
                      "offset": 0, "marker_offset": 0, "payload_offset": 2, "declared_length": None,
                      "payload_length": 0, "end_offset": 2, "category": "boundary", "summary": "SOI",
                      "metadata": None}],
        "scans": [], "frames": [], "quantization_tables": [], "huffman_tables": [], "exif": [],
        "xmp": [], "icc": [], "visual_assets": [], "comments": [],
        "warnings": [{"code": "trailing_bytes", "message": "2 bytes after EOI", "offset": 6}],
        "capabilities": {"segment_raw": True, "scan_raw": True, "exif_navigation": True,
                         "xmp_text": True, "icc_reconstruction": True, "lazy_visual_assets": True},
    }


class _Native:
    def report_json(self) -> str: return json.dumps(_report())
    def get_segment(self, index: int) -> str: return json.dumps(_report()["segments"][index])
    def get_segment_raw(self, _index: int) -> bytes: return b"\xff\xd8"
    def get_scan(self, _index: int) -> str: return "{}"
    def get_scan_raw(self, _index: int) -> bytes: return b"scan"
    def get_exif_ifd(self, path: str) -> str: return json.dumps({"id": path})
    def get_exif_entry(self, path: str, tag_id: int) -> str: return json.dumps({"path": path, "tag_id": tag_id})
    def get_visual_asset(self, _asset_id: str) -> bytes: return b"asset"
    def get_preview(self, _asset_id: str) -> bytes: return b"jpeg"
    def get_xmp_text(self, _packet_id: str) -> str: return "<xmp/>"
    def get_xmp_raw(self, _packet_id: str) -> bytes: return b"<xmp/>"
    def get_icc_profile(self) -> bytes: return b"icc"
    def get_trailing_bytes(self) -> bytes: return b"xx"


def test_typed_jpeg_facade_and_lazy_access(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls = []
    monkeypatch.setitem(sys.modules, "forensihash_core", SimpleNamespace(analyze_jpeg=lambda *args: calls.append(args) or _Native()))
    path = tmp_path / "evidence.bin"; path.write_bytes(b"\xff\xd8\xff\xd9xx")
    session = DeepFileStructureEngine(max_file_bytes=99).analyze_jpeg(path, max_segments=20)
    assert session.report.structure_version == "1.0"
    assert session.report.segments[0].marker_name == "SOI"
    assert session.get_segment_raw(0) == b"\xff\xd8"
    assert session.get_exif_entry("IFD0", 0x0112)["tag_id"] == 0x0112
    assert session.get_preview() == b"jpeg"
    assert session.get_trailing_bytes() == b"xx"
    assert calls[0][0:3] == (str(path), 99, 20)


def test_non_jpeg_native_error_is_unsupported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "forensihash_core", SimpleNamespace(analyze_jpeg=lambda *_: (_ for _ in ()).throw(RuntimeError("JPEG SOI/marker structure not found"))))
    path = tmp_path / "text.jpg"; path.write_bytes(b"text")
    with pytest.raises(DeepStructureError) as captured: DeepFileStructureEngine().analyze_jpeg(path)
    assert captured.value.category == "unsupported"


def test_native_oserror_is_wrapped_and_keeps_cause(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def fail(*_args):
        raise OSError(22, "Invalid argument")

    monkeypatch.setitem(sys.modules, "forensihash_core", SimpleNamespace(analyze_jpeg=fail))
    path = tmp_path / "0000.jpg"
    path.write_bytes(b"\xff\xd8\xff\xd9")
    with pytest.raises(DeepStructureError) as captured:
        DeepFileStructureEngine().analyze_jpeg(path)
    assert captured.value.category == "malformed"
    assert isinstance(captured.value.__cause__, OSError)


def test_jpeg_limits_must_be_positive(tmp_path: Path) -> None:
    with pytest.raises(ValueError): DeepFileStructureEngine().analyze_jpeg(tmp_path / "x", max_scans=0)


def test_real_native_jpeg_progressive_offsets_and_preview(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    image = pytest.importorskip("PIL.Image")
    path = tmp_path / "progressive.jpg"
    image.new("RGB", (32, 24), (20, 80, 140)).save(path, "JPEG", progressive=True, comment=b"forensihash")
    source = path.read_bytes()
    session = DeepFileStructureEngine().analyze_jpeg(path)
    assert session.report.format == "jpeg"
    assert any(frame["frame_type"] == "progressive_dct" for frame in session.report.frames)
    assert len(session.report.scans) > 1
    for segment in session.report.segments:
        assert session.get_segment_raw(segment.index) == source[segment.offset:segment.end_offset]
    assert session.get_preview() == source


def test_real_native_trailing_and_concatenated_signature(tmp_path: Path) -> None:
    pytest.importorskip("forensihash_core")
    path = tmp_path / "trailing.jpg"; path.write_bytes(b"\xff\xd8\xff\xd9tail\xff\xd8")
    session = DeepFileStructureEngine().analyze_jpeg(path)
    assert session.report.physical_info.trailing_bytes_length == 6
    assert session.get_trailing_bytes() == b"tail\xff\xd8"
    assert {warning.code for warning in session.report.warnings} >= {"trailing_bytes", "trailing_jpeg_signature"}

import hashlib
import json
from pathlib import Path

import pytest

from app.services.byte_range_extraction_service import ByteRangeError, ByteRangeExtractionService


def test_read_range_at_start_middle_and_final_byte(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"; source.write_bytes(bytes(range(64)))
    service = ByteRangeExtractionService(max_read_bytes=64)
    assert service.read_range(source, 0, 4) == bytes(range(4))
    assert service.read_range(source, 10, 5) == bytes(range(10, 15))
    assert service.read_range(source, 63, 1) == b"\x3f"


@pytest.mark.parametrize("offset,length,category", [(-1, 1, "invalid_range"), (0, 0, "invalid_range"),
                                                       (9, 2, "invalid_range"), (0, 9, "limit_exceeded")])
def test_read_range_rejects_invalid_bounds_and_limit(tmp_path: Path, offset: int, length: int,
                                                     category: str) -> None:
    source = tmp_path / "source.bin"; source.write_bytes(b"0123456789")
    with pytest.raises(ByteRangeError) as captured:
        ByteRangeExtractionService(max_read_bytes=8).read_range(source, offset, length)
    assert captured.value.category == category


def test_extract_preserves_origin_hashes_region_detects_type_and_writes_sidecar(tmp_path: Path) -> None:
    jpeg = b"\xff\xd8\xff\xe0\x00\x02\xff\xd9"
    source_bytes = b"prefix" + jpeg + b"suffix"
    source = tmp_path / "evidence.bin"; source.write_bytes(source_bytes)
    destination = tmp_path / "derived.jpg"
    artifact = ByteRangeExtractionService().extract(source, destination, 6, len(jpeg), write_sidecar=True)
    assert source.read_bytes() == source_bytes
    assert destination.read_bytes() == jpeg
    assert artifact.start_offset == 6 and artifact.end_offset == 6 + len(jpeg) - 1
    assert artifact.source_sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert artifact.extracted_sha256 == hashlib.sha256(jpeg).hexdigest()
    assert artifact.detected_format == "JPEG" and artifact.detected_mime == "image/jpeg"
    sidecar = Path(f"{destination}.forensihash.json")
    payload = json.loads(sidecar.read_text(encoding="utf-8"))
    assert payload["extraction_method"] == "hex_selection" and payload["source_file"] == "evidence.bin"


def test_hash_and_type_detection_reuse_engines(tmp_path: Path) -> None:
    source = tmp_path / "container.bin"; source.write_bytes(b"xx%PDF-1.7\n%%EOFxx")
    service = ByteRangeExtractionService()
    assert service.hash_range(source, 2, 14) == hashlib.sha256(b"%PDF-1.7\n%%EOF").hexdigest()
    detected = service.detect_range(source, 2, 14)
    assert detected.detected_format == "PDF"


def test_extraction_never_allows_source_as_destination(tmp_path: Path) -> None:
    source = tmp_path / "same.bin"; source.write_bytes(b"original")
    with pytest.raises(ByteRangeError): ByteRangeExtractionService().extract(source, source, 0, 4)
    assert source.read_bytes() == b"original"

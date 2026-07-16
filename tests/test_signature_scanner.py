from pathlib import Path

import pytest

from app.binary import BinaryReader, SignatureScanner


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        (b"%PDF-1.7", "pdf"),
        (b"PK\x03\x04data", "zip"),
        (b"SQLite format 3\x00data", "sqlite"),
    ],
)
def test_recognizes_signature_at_zero(
    tmp_path: Path, content: bytes, kind: str
) -> None:
    path = tmp_path / "file.bin"
    path.write_bytes(content)
    region = SignatureScanner().scan(BinaryReader(path))[0]
    assert region.offset == 0
    assert region.kind == kind
    assert region.status == "recognized"


def test_internal_repeated_signatures_are_candidates_and_sorted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "mixed.bin"
    path.write_bytes(b"%PDF-x\xff\xd8\xff-yPK\x03\x04-z\xff\xd8\xff")
    regions = SignatureScanner().scan(BinaryReader(path))
    assert [region.offset for region in regions] == sorted(
        region.offset for region in regions
    )
    jpeg = [region for region in regions if "jpeg" in region.kind]
    assert len(jpeg) == 2
    assert all(region.kind == "candidate_jpeg" for region in jpeg)
    assert all(region.status == "candidate" for region in jpeg)
    assert jpeg[0].signature == "FFD8FF"


def test_empty_absent_and_per_signature_limit(tmp_path: Path) -> None:
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    assert SignatureScanner().scan(BinaryReader(empty)) == []
    absent = tmp_path / "absent.bin"
    absent.write_bytes(b"plain data")
    assert SignatureScanner().scan(BinaryReader(absent)) == []
    repeated = tmp_path / "repeated.bin"
    repeated.write_bytes(b"x\xff\xd8\xffy\xff\xd8\xffz")
    regions = SignatureScanner().scan(
        BinaryReader(repeated), max_results_per_signature=1
    )
    assert len([item for item in regions if "jpeg" in item.kind]) == 1

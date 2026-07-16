from pathlib import Path

import pytest

from app.binary import BinaryReader


def test_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.bin"
    path.write_bytes(b"")
    reader = BinaryReader(path)
    assert reader.size == 0
    assert reader.is_empty
    assert reader.read_header(10) == b""
    assert reader.read_footer(10) == b""
    assert list(reader.iter_chunks(4)) == []


def test_reads_boundaries_header_footer_and_chunks(tmp_path: Path) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"0123456789")
    reader = BinaryReader(path)
    assert reader.read_at(0, 10) == b"0123456789"
    assert reader.read_at(4, 3) == b"456"
    assert reader.read_at(9, 1) == b"9"
    assert reader.read_at(8, 20) == b"89"
    assert reader.read_header(3) == b"012"
    assert reader.read_footer(3) == b"789"
    assert list(reader.iter_chunks(4))[-1] == (8, b"89")


@pytest.mark.parametrize("offset,length", [(-1, 1), (0, -1)])
def test_negative_read_is_rejected(
    tmp_path: Path, offset: int, length: int
) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"x")
    with pytest.raises(ValueError):
        BinaryReader(path).read_at(offset, length)


@pytest.mark.parametrize("overlap", [-1, 4, 5])
def test_invalid_overlap(tmp_path: Path, overlap: int) -> None:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"content")
    with pytest.raises(ValueError):
        list(BinaryReader(path).iter_chunks(4, overlap))


def test_find_bytes_offsets_boundary_and_limit(tmp_path: Path) -> None:
    path = tmp_path / "search.bin"
    content = b"AB" + (b"x" * (BinaryReader.SEARCH_CHUNK_SIZE - 3)) + b"ABAB"
    path.write_bytes(content)
    reader = BinaryReader(path)
    offsets = reader.find_bytes(b"AB", max_results=10)
    assert offsets[0] == 0
    assert BinaryReader.SEARCH_CHUNK_SIZE - 1 in offsets
    assert reader.find_bytes(b"AB", max_results=2) == offsets[:2]


def test_hex_dump_is_deterministic(tmp_path: Path) -> None:
    path = tmp_path / "dump.bin"
    path.write_bytes(b"A\x00BC")
    assert BinaryReader(path).hex_dump(0, 4, width=2) == (
        "00000000  41 00  A.\n00000002  42 43  BC"
    )

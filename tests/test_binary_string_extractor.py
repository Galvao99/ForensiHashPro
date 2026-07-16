from pathlib import Path

from app.binary import BinaryReader, BinaryStringExtractor


def _extract(path: Path, **kwargs):
    return BinaryStringExtractor(**kwargs).extract(BinaryReader(path))


def test_ascii_utf16_offsets_and_no_obvious_ascii_duplication(
    tmp_path: Path,
) -> None:
    path = tmp_path / "strings.bin"
    ascii_value = b"HELLO"
    le_value = "Mundo".encode("utf-16-le")
    be_value = "Teste".encode("utf-16-be")
    path.write_bytes(b"\x00" + ascii_value + b"\x00" + le_value + b"\x00" + be_value)
    strings = _extract(path, minimum_length=5, chunk_size=3)
    matches = {(item.encoding, item.value): item for item in strings}
    assert matches[("ascii", "HELLO")].offset == 1
    assert matches[("utf-16-le", "Mundo")].offset == 7
    assert matches[("utf-16-be", "Teste")].offset == 18
    assert len([item for item in strings if item.value == "HELLO"]) == 1


def test_cross_chunk_minimum_limit_and_no_strings(tmp_path: Path) -> None:
    path = tmp_path / "cross.bin"
    path.write_bytes(b"xx\x00CROSSING\x00SECOND\x00")
    strings = _extract(
        path, minimum_length=6, maximum_results=1, chunk_size=4
    )
    assert len(strings) == 1
    assert strings[0].value == "CROSSING"
    assert strings[0].offset == 3

    none = tmp_path / "none.bin"
    none.write_bytes(b"\x00\x01\x02\x03")
    assert _extract(none, minimum_length=4, chunk_size=2) == []


def test_control_characters_are_preserved(tmp_path: Path) -> None:
    path = tmp_path / "controls.bin"
    path.write_bytes(b"line1\nline2\x00")
    result = _extract(path, minimum_length=4)[0]
    assert result.value == "line1\nline2"
    assert result.length == 11

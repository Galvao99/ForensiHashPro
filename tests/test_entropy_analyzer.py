from pathlib import Path

from app.binary import BinaryReader, EntropyAnalyzer


def test_empty_and_uniform_files(tmp_path: Path) -> None:
    empty = tmp_path / "empty.bin"
    empty.write_bytes(b"")
    analyzer = EntropyAnalyzer(block_size=4)
    assert analyzer.analyze(BinaryReader(empty)) == []
    assert analyzer.weighted_average([]) is None

    uniform = tmp_path / "uniform.bin"
    uniform.write_bytes(b"A" * 8)
    regions = analyzer.analyze(BinaryReader(uniform))
    assert all(region.entropy == 0.0 for region in regions)
    assert all(region.classification == "low" for region in regions)


def test_partial_block_range_classification_and_weighted_average(
    tmp_path: Path,
) -> None:
    path = tmp_path / "varied.bin"
    path.write_bytes(bytes(range(10)))
    analyzer = EntropyAnalyzer(block_size=8)
    regions = analyzer.analyze(BinaryReader(path))
    assert [region.length for region in regions] == [8, 2]
    assert all(0 <= region.entropy <= 8 for region in regions)
    expected = sum(r.entropy * r.length for r in regions) / 10
    assert analyzer.weighted_average(regions) == expected
    assert analyzer.classify(2.9) == "low"
    assert analyzer.classify(3.0) == "moderate"
    assert analyzer.classify(5.5) == "high"
    assert analyzer.classify(7.5) == "very_high"

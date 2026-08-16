from pathlib import Path

from app.engines.hash_engine import HashEngine


def test_calculate_all_reads_file_once_and_matches_individual_algorithms(
    tmp_path: Path,
    monkeypatch,
) -> None:
    evidence = tmp_path / "evidence.bin"
    evidence.write_bytes((b"ForensiHash\x00" * 100_000) + b"final")
    engine = HashEngine()
    expected = {
        algorithm: engine.calculate_file_hash(evidence, algorithm)
        for algorithm in engine._algorithms
    }

    original_open = Path.open
    open_count = 0

    def counted_open(path: Path, *args, **kwargs):
        nonlocal open_count
        if path == evidence and args and args[0] == "rb":
            open_count += 1
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", counted_open)
    result = engine.calculate_all(evidence)

    assert open_count == 1
    assert {
        algorithm: getattr(result, algorithm)
        for algorithm in engine._algorithms
    } == expected

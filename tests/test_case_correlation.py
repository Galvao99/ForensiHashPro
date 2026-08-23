from pathlib import Path
from types import SimpleNamespace

from app.services.correlation_service import CorrelationService


def result(path: Path, *, sha256: str, text: str = "") -> SimpleNamespace:
    return SimpleNamespace(
        file_info=SimpleNamespace(name=path.name, path=path),
        extracted_text=text,
        hashes=SimpleNamespace(sha256=sha256),
        metadata=SimpleNamespace(raw={}),
        digital_signature=None,
        timeline_events=[],
        processing_steps=[],
        resolved_entities=[],
        json_analysis=None,
    )


def categories(correlation) -> list[str]:
    return [finding.category for finding in correlation.findings]


def test_declared_sha256_matches_file_in_same_case(tmp_path: Path) -> None:
    value = "b" * 64
    source = result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    target = result(tmp_path / "B.jpg", sha256=value)

    correlation = CorrelationService().update_case("case-1", [source, target])

    finding = next(item for item in correlation.findings if item.category == "embedded_hash_match")
    assert finding.source_file == "A.pdf"
    assert finding.target_file == "B.jpg"
    assert finding.metadata["match_type"] == "exact_cryptographic_match"
    assert finding.metadata["calculated_hash"] == value


def test_declared_sha256_without_case_match_is_unmatched(tmp_path: Path) -> None:
    source = result(
        tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {'c' * 64}"
    )

    correlation = CorrelationService().update_case("case-1", [source])

    assert "embedded_hash_unmatched" in categories(correlation)


def test_same_declared_hash_in_multiple_documents_is_consistent(tmp_path: Path) -> None:
    value = "b" * 64
    first = result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    second = result(tmp_path / "C.pdf", sha256="c" * 64, text=f"SHA-256: {value}")
    target = result(tmp_path / "B.jpg", sha256=value)
    service = CorrelationService()

    initial = service.update_case("case-1", [first, second, target])
    repeated = service.update_case("case-1", [first, second, target])

    matches = [item for item in initial.findings if item.category == "embedded_hash_match"]
    assert {(item.source_file, item.target_file) for item in matches} == {
        ("A.pdf", "B.jpg"), ("C.pdf", "B.jpg")
    }
    assert [item.finding_id for item in initial.findings] == [
        item.finding_id for item in repeated.findings
    ]
    assert len({item.finding_id for item in repeated.findings}) == len(repeated.findings)


def test_equal_hash_outside_case_is_not_correlated(tmp_path: Path) -> None:
    value = "b" * 64
    source = result(tmp_path / "case" / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    outside = result(tmp_path / "other" / "B.jpg", sha256=value)
    service = CorrelationService()
    service.update_case("other-case", [outside])

    correlation = service.update_case("case-1", [source])

    assert "embedded_hash_match" not in categories(correlation)
    assert "embedded_hash_unmatched" in categories(correlation)


def test_add_matching_file_updates_only_correlation(tmp_path: Path) -> None:
    value = "b" * 64
    source = result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    target = result(tmp_path / "B.jpg", sha256=value)
    service = CorrelationService()
    service.update_case("case-1", [source])

    correlation = service.add_to_case("case-1", target)

    assert "embedded_hash_match" in categories(correlation)
    assert service._case_indexes["case-1"].results == (source, target)


def test_remove_matching_file_updates_correlation(tmp_path: Path) -> None:
    value = "b" * 64
    source = result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    target = result(tmp_path / "B.jpg", sha256=value)
    service = CorrelationService()
    service.update_case("case-1", [source, target])

    correlation = service.remove_from_case("case-1", target.file_info.path)

    assert "embedded_hash_match" not in categories(correlation)
    assert "embedded_hash_unmatched" in categories(correlation)


def test_repeated_selection_equivalent_update_is_idempotent(tmp_path: Path) -> None:
    value = "b" * 64
    source = result(tmp_path / "A.pdf", sha256="a" * 64, text=f"SHA-256: {value}")
    target = result(tmp_path / "B.jpg", sha256=value)
    service = CorrelationService()

    first = service.update_case("case-1", [source, target])
    context = service._case_indexes["case-1"].context
    for _ in range(5):
        current = service.update_case("case-1", [source, target])
        assert service._case_indexes["case-1"].context is context
        assert [item.finding_id for item in current.findings] == [
            item.finding_id for item in first.findings
        ]

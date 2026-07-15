from pathlib import Path

from app.presentation.file_display import (
    build_file_displays,
    folder_display_origin,
)


def _origins(*paths: str) -> dict[str, str]:
    displays = build_file_displays(Path(path) for path in paths)
    return {
        path: displays[str(Path(path))].display_origin
        for path in paths
    }


def test_different_file_names_use_minimal_safe_origin() -> None:
    paths = (
        "C:/case-a/documents/alpha.pdf",
        "C:/case-a/documents/beta.pdf",
    )

    origins = _origins(*paths)

    assert origins[paths[0]] == "documents"
    assert origins[paths[1]] == "documents"


def test_homonyms_in_different_immediate_folders_are_distinct() -> None:
    paths = (
        "C:/case-a/documents/evidence.pdf",
        "C:/case-b/images/evidence.pdf",
    )

    origins = _origins(*paths)

    assert origins[paths[0]] == "documents"
    assert origins[paths[1]] == "images"


def test_homonyms_expand_until_ancestor_is_distinct() -> None:
    paths = (
        "C:/case-a/documents/evidence.pdf",
        "D:/case-b/documents/evidence.pdf",
    )

    origins = _origins(*paths)

    assert origins[paths[0]] == "case-a/documents"
    assert origins[paths[1]] == "case-b/documents"


def test_different_drives_never_appear_in_origin() -> None:
    paths = (
        "C:/case-a/documents/evidence.pdf",
        "D:/case-b/documents/evidence.pdf",
    )

    origins = _origins(*paths)
    rendered = "\n".join(origins.values())

    assert "C:" not in rendered
    assert "D:" not in rendered
    assert len(set(origins.values())) == 2


def test_personal_directories_are_removed() -> None:
    path = "C:/Users/private/OneDrive/Desktop/case/evidence.pdf"

    origin = _origins(path)[path]

    assert origin == "case"
    for private_value in ("C:", "Users", "private", "OneDrive", "Desktop"):
        assert private_value not in origin


def test_folder_origin_is_safe() -> None:
    path = "C:/Users/private/OneDrive/Desktop/case-a"

    origin = folder_display_origin(path)

    assert origin == "case-a"
    for private_value in ("C:", "Users", "private", "OneDrive", "Desktop"):
        assert private_value not in origin

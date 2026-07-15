from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class FileDisplay:
    display_name: str
    display_origin: str


def build_file_displays(
    paths: Iterable[str | Path],
) -> dict[str, FileDisplay]:
    normalized_paths = [Path(path) for path in paths]
    components = {
        str(path): _safe_parent_components(path)
        for path in normalized_paths
    }
    displays: dict[str, FileDisplay] = {}

    for path in normalized_paths:
        key = str(path)
        peers = [
            peer
            for peer in normalized_paths
            if peer.name.casefold() == path.name.casefold()
            and str(peer) != key
        ]
        origin_parts = components[key]
        origin = _minimal_unique_origin(
            path,
            origin_parts,
            peers,
            components,
        )
        displays[key] = FileDisplay(
            display_name=path.name or "Arquivo sem nome",
            display_origin=origin,
        )

    return displays


def file_display(
    path: str | Path | None,
    peer_paths: Iterable[str | Path] = (),
) -> FileDisplay:
    if not path:
        return FileDisplay(
            display_name="Arquivo sem nome",
            display_origin="Origem não informada",
        )

    current_path = Path(path)
    paths = [current_path, *[Path(peer) for peer in peer_paths]]
    return build_file_displays(paths)[str(current_path)]


def folder_display_origin(path: str | Path | None) -> str:
    if not path:
        return "Origem não informada"

    components = _safe_path_components(Path(path))
    return components[-1] if components else "Origem não informada"


def _minimal_unique_origin(
    path: Path,
    origin_parts: tuple[str, ...],
    peers: list[Path],
    components: dict[str, tuple[str, ...]],
) -> str:
    if not origin_parts:
        return "Origem não informada"

    if not peers:
        return origin_parts[-1]

    for depth in range(1, len(origin_parts) + 1):
        candidate = origin_parts[-depth:]
        if all(
            candidate
            != components[str(peer)][-depth:]
            for peer in peers
        ):
            return "/".join(candidate)

    relative_origin = "/".join(origin_parts)
    collision_token = sha256(
        str(path).encode("utf-8")
    ).hexdigest()[:6]
    return f"{relative_origin} • origem {collision_token}"


def _safe_parent_components(path: Path) -> tuple[str, ...]:
    return _safe_path_components(path.parent)


def _safe_path_components(path: Path) -> tuple[str, ...]:
    parts = [
        part
        for part in path.parts
        if part not in {path.anchor, "\\", "/"}
        and not part.endswith(":\\")
        and not part.endswith(":")
    ]
    folded = [part.casefold() for part in parts]

    if "users" in folded:
        user_index = folded.index("users")
        parts = parts[user_index + 2 :]

    personal_roots = {
        "desktop",
        "documents",
        "downloads",
        "onedrive",
    }
    while parts and (
        parts[0].casefold() in personal_roots
        or parts[0].casefold().startswith("onedrive - ")
    ):
        parts.pop(0)

    return tuple(parts)

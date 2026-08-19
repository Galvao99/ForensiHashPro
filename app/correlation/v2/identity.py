from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from app.correlation.v2.models import SourceFileIdentity


def stable_digest(namespace: str, payload: Any) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(f"forensihash:correlation:v2:{namespace}:{canonical}".encode("utf-8")).hexdigest()


def source_file_identity(
    *, display_name: str, sha256: str | None = None, path: str | Path | None = None,
    session_id: str | None = None,
) -> SourceFileIdentity:
    normalized_hash = sha256.strip().lower() if sha256 else None
    normalized_path = os.path.normcase(os.path.abspath(os.fspath(path))) if path is not None else None
    identity_material: dict[str, str] = {}
    if session_id:
        identity_material["session_id"] = session_id
    if normalized_path:
        identity_material["path"] = normalized_path
    if not identity_material and normalized_hash:
        identity_material["sha256"] = normalized_hash
        identity_material["display_name"] = display_name
    if not identity_material:
        identity_material["display_name"] = display_name
    return SourceFileIdentity(
        stable_id=stable_digest("file", identity_material), display_name=display_name,
        sha256=normalized_hash, path=normalized_path, session_id=session_id,
    )

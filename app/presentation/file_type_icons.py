from __future__ import annotations

from pathlib import Path


_FILE_TYPE_ICONS = {
    ".pdf": "file-type-pdf", ".jpg": "file-type-jpg", ".jpeg": "file-type-jpg",
    ".png": "file-type-png", ".json": "braces", ".sql": "file-type-sql", ".csv": "file-type-csv",
    ".txt": "file-type-txt", ".zip": "file-type-zip", ".docx": "file-type-docx",
    ".xlsx": "file-type-xls", ".xls": "file-type-xls", ".pptx": "file-type-ppt",
    ".ppt": "file-type-ppt", ".xml": "file-type-xml", ".html": "file-type-html",
    ".htm": "file-type-html", ".eml": "mail", ".msg": "mail",
}


def file_type_icon_name(filename: str) -> str:
    """Return a vendored Tabler icon name; unknown formats use generic file."""
    return _FILE_TYPE_ICONS.get(Path(filename).suffix.casefold(), "file")


def file_extension_label(filename: str) -> str:
    return Path(filename).suffix.lstrip(".").upper() or "ARQUIVO"

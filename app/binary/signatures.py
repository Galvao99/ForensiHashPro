"""Canonical byte prefixes shared by binary and magic-number analysis."""

BINARY_SIGNATURES: dict[str, bytes] = {
    "pdf": b"%PDF",
    "jpeg": b"\xFF\xD8\xFF",
    "png": b"\x89PNG\r\n\x1A\n",
    "zip": b"PK\x03\x04",
    "rar": b"Rar!",
    "7z": b"7z\xBC\xAF\x27\x1C",
    "sqlite": b"SQLite format 3\x00",
}

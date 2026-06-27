import json
import subprocess
from pathlib import Path
from typing import Any

from app.models import MetadataResult


class MetadataEngine:
    """Responsável por extrair metadados usando o ExifTool."""

    def __init__(self, exiftool_path: Path | None = None) -> None:
        self.exiftool_path = exiftool_path or Path("tools/exiftool.exe")

    def extract(self, file_path: Path) -> MetadataResult:
        if not self.exiftool_path.exists():
            raise FileNotFoundError(f"ExifTool não encontrado: {self.exiftool_path}")

        command = [
            str(self.exiftool_path),
            "-json",
            "-G",
            "-a",
            "-u",
            str(file_path),
        ]

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())

        data: list[dict[str, Any]] = json.loads(result.stdout)

        if not data:
            return MetadataResult(raw={})

        return MetadataResult(raw=data[0])
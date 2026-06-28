from pathlib import Path

from app.models import MagicNumberResult


class MagicNumberEngine:
    """Identifica o tipo real do arquivo pela assinatura binária."""

    SIGNATURES: dict[bytes, str] = {
        b"%PDF": "PDF",
        bytes.fromhex("89504E47"): "PNG",
        bytes.fromhex("FFD8FF"): "JPEG",
        bytes.fromhex("47494638"): "GIF",
        bytes.fromhex("424D"): "BMP",
        bytes.fromhex("504B0304"): "ZIP",
        bytes.fromhex("52617221"): "RAR",
        bytes.fromhex("377ABCAF271C"): "7Z",
    }

    EXTENSION_MAP: dict[str, set[str]] = {
        ".pdf": {"PDF"},
        ".png": {"PNG"},
        ".jpg": {"JPEG"},
        ".jpeg": {"JPEG"},
        ".gif": {"GIF"},
        ".bmp": {"BMP"},
        ".zip": {"ZIP"},
        ".docx": {"ZIP"},
        ".xlsx": {"ZIP"},
        ".pptx": {"ZIP"},
        ".rar": {"RAR"},
        ".7z": {"7Z"},
    }

    def analyze(self, file_path: Path) -> MagicNumberResult:
        header = self._read_header(file_path)

        detected_type = "Desconhecido"
        signature = header[:16].hex(" ").upper()

        for magic, file_type in self.SIGNATURES.items():
            if header.startswith(magic):
                detected_type = file_type
                signature = magic.hex(" ").upper()
                break

        expected_types = self.EXTENSION_MAP.get(
            file_path.suffix.lower(),
            set(),
        )

        extension_matches = (
            detected_type in expected_types
            if expected_types
            else False
        )

        return MagicNumberResult(
            detected_type=detected_type,
            signature=signature,
            extension_matches=extension_matches,
        )

    def _read_header(self, file_path: Path, size: int = 32) -> bytes:
        with file_path.open("rb") as file:
            return file.read(size)
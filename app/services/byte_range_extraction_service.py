from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile, TemporaryDirectory

from app.engines.hash_engine import HashEngine
from app.engines.magic_number_engine import MagicNumberEngine
from app.models.extracted_artifact import ExtractedArtifact


class ByteRangeError(ValueError):
    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


class ByteRangeExtractionService:
    """Lê e deriva faixas limitadas sem modificar o arquivo de origem."""

    def __init__(self, *, hash_engine: HashEngine | None = None,
                 magic_number_engine: MagicNumberEngine | None = None,
                 max_read_bytes: int = 128 * 1024 * 1024,
                 max_extract_bytes: int = 512 * 1024 * 1024) -> None:
        if max_read_bytes <= 0 or max_extract_bytes <= 0:
            raise ValueError("byte range limits must be greater than zero")
        self.hash_engine = hash_engine or HashEngine()
        self.magic_number_engine = magic_number_engine or MagicNumberEngine()
        self.max_read_bytes = max_read_bytes
        self.max_extract_bytes = max_extract_bytes

    def read_range(self, source_path: str | Path, offset: int, length: int, *,
                   maximum_bytes: int | None = None) -> bytes:
        source = Path(source_path)
        limit = self.max_read_bytes if maximum_bytes is None else min(maximum_bytes, self.max_read_bytes)
        self._validate(source, offset, length, limit)
        with source.open("rb") as stream:
            stream.seek(offset)
            data = stream.read(length)
        if len(data) != length:
            raise ByteRangeError("malformed", "A faixa solicitada não pôde ser lida integralmente.")
        return data

    def hash_range(self, source_path: str | Path, offset: int, length: int,
                   algorithm: str = "sha256") -> str:
        data = self.read_range(source_path, offset, length)
        return self.hash_engine.calculate_bytes_hash(data, algorithm)

    def detect_range(self, source_path: str | Path, offset: int, length: int):
        data = self.read_range(source_path, offset, length)
        with TemporaryDirectory(prefix="forensihash-selection-") as directory:
            temporary = Path(directory) / "selection.bin"
            temporary.write_bytes(data)
            return self.magic_number_engine.analyze(temporary)

    def extract(self, source_path: str | Path, destination_path: str | Path, offset: int, length: int,
                *, source_sha256: str | None = None, write_sidecar: bool = False) -> ExtractedArtifact:
        source, destination = Path(source_path), Path(destination_path)
        self._validate(source, offset, length, self.max_extract_bytes)
        if source.resolve() == destination.resolve():
            raise ByteRangeError("invalid_range", "O destino não pode substituir o arquivo de origem.")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with NamedTemporaryFile(prefix=f".{destination.name}.", suffix=".part",
                                    dir=destination.parent, delete=False) as output_stream:
                temporary_path = Path(output_stream.name)
                remaining = length
                with source.open("rb") as input_stream:
                    input_stream.seek(offset)
                    while remaining:
                        chunk = input_stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            raise ByteRangeError("malformed", "A origem terminou antes do fim da faixa selecionada.")
                        output_stream.write(chunk)
                        remaining -= len(chunk)
            os.replace(temporary_path, destination)
        except BaseException:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
        extracted_sha256 = self.hash_engine.calculate_file_hash(destination, "sha256")
        origin_sha256 = source_sha256 or self.hash_engine.calculate_file_hash(source, "sha256")
        detected = self.magic_number_engine.analyze(destination)
        artifact = ExtractedArtifact(
            source_path=source, destination_path=destination, source_sha256=origin_sha256,
            start_offset=offset, end_offset=offset + length - 1, length=length,
            extracted_sha256=extracted_sha256, detected_format=detected.detected_format,
            detected_mime=detected.mime_type, signature=detected.signature,
        )
        if write_sidecar:
            self.write_sidecar(artifact)
        return artifact

    @staticmethod
    def write_sidecar(artifact: ExtractedArtifact) -> Path:
        sidecar = Path(f"{artifact.destination_path}.forensihash.json")
        payload = artifact.to_dict()
        payload["source_file"] = artifact.source_path.name
        payload["sha256"] = artifact.extracted_sha256
        sidecar.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return sidecar

    @staticmethod
    def _validate(source: Path, offset: int, length: int, limit: int) -> None:
        if not source.is_file():
            raise ByteRangeError("unsupported", "O arquivo de origem não está disponível.")
        if offset < 0 or length <= 0:
            raise ByteRangeError("invalid_range", "Offset deve ser não negativo e length deve ser positivo.")
        if length > limit:
            raise ByteRangeError("limit_exceeded", f"A faixa excede o limite configurado de {limit} bytes.")
        size = source.stat().st_size
        end = offset + length
        if end < offset or end > size:
            raise ByteRangeError("invalid_range", "A faixa solicitada ultrapassa o fim do arquivo.")

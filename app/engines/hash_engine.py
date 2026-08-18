import hashlib
from pathlib import Path

from app.models import HashResult


class HashEngine: #Colocar mais hashes se necessário
    """Responsável por calcular hashes de arquivos."""

    _algorithms: dict[str, str] = {
        "md5": "md5",
        "sha1": "sha1",
        "sha224": "sha224",
        "sha256": "sha256",
        "sha384": "sha384",
        "sha512": "sha512",
    }

    def calculate_file_hash(self, file_path: Path, algorithm: str) -> str:
        if algorithm not in self._algorithms:
            raise ValueError(f"Algoritmo de hash não suportado: {algorithm}")

        hash_object = hashlib.new(self._algorithms[algorithm])

        with file_path.open("rb") as file:
            for chunk in iter(lambda: file.read(8192), b""):
                hash_object.update(chunk)

        return hash_object.hexdigest()

    def calculate_bytes_hash(self, data: bytes | bytearray | memoryview, algorithm: str) -> str:
        """Calcula o digest de uma região já limitada em memória."""
        if algorithm not in self._algorithms:
            raise ValueError(f"Algoritmo de hash não suportado: {algorithm}")
        hash_object = hashlib.new(self._algorithms[algorithm])
        hash_object.update(data)
        return hash_object.hexdigest()

    def calculate_all(self, file_path: Path) -> HashResult:
        hash_objects = {
            name: hashlib.new(algorithm)
            for name, algorithm in self._algorithms.items()
        }
        with Path(file_path).open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                for hash_object in hash_objects.values():
                    hash_object.update(chunk)
        return HashResult(**{
            name: hash_object.hexdigest()
            for name, hash_object in hash_objects.items()
        })

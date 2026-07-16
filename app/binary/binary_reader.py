from collections.abc import Iterator
from pathlib import Path


class BinaryReader:
    """Bounded, stateless access to a file's bytes."""

    SEARCH_CHUNK_SIZE = 64 * 1024

    def __init__(self, path: Path) -> None:
        self._path = Path(path)
        self._size = self._path.stat().st_size

    @property
    def path(self) -> Path:
        return self._path

    @property
    def size(self) -> int:
        return self._size

    @property
    def is_empty(self) -> bool:
        return self._size == 0

    def read_at(self, offset: int, length: int) -> bytes:
        self._validate_non_negative("offset", offset)
        self._validate_non_negative("length", length)
        if offset >= self._size or length == 0:
            return b""
        with self._path.open("rb") as stream:
            stream.seek(offset)
            return stream.read(min(length, self._size - offset))

    def read_header(self, length: int) -> bytes:
        return self.read_at(0, length)

    def read_footer(self, length: int) -> bytes:
        self._validate_non_negative("length", length)
        actual_length = min(length, self._size)
        return self.read_at(self._size - actual_length, actual_length)

    def iter_chunks(
        self,
        chunk_size: int,
        overlap: int = 0,
    ) -> Iterator[tuple[int, bytes]]:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must satisfy 0 <= overlap < chunk_size")
        step = chunk_size - overlap
        with self._path.open("rb") as stream:
            offset = 0
            while offset < self._size:
                stream.seek(offset)
                chunk = stream.read(min(chunk_size, self._size - offset))
                if not chunk:
                    break
                yield offset, chunk
                offset += step

    def find_bytes(
        self,
        pattern: bytes,
        start: int = 0,
        end: int | None = None,
        max_results: int = 100,
    ) -> list[int]:
        if not isinstance(pattern, bytes) or not pattern:
            raise ValueError("pattern must be non-empty bytes")
        self._validate_non_negative("start", start)
        if end is not None:
            self._validate_non_negative("end", end)
            if end < start:
                raise ValueError("end must not be smaller than start")
        if max_results <= 0:
            raise ValueError("max_results must be greater than zero")

        stop = min(self._size, self._size if end is None else end)
        if start >= stop:
            return []
        results: list[int] = []
        overlap = len(pattern) - 1
        chunk_size = max(self.SEARCH_CHUNK_SIZE, len(pattern))
        position = start
        carry = b""
        with self._path.open("rb") as stream:
            stream.seek(start)
            while position < stop and len(results) < max_results:
                block = stream.read(min(chunk_size, stop - position))
                if not block:
                    break
                data = carry + block
                base = position - len(carry)
                search_from = 0
                while len(results) < max_results:
                    index = data.find(pattern, search_from)
                    if index < 0:
                        break
                    absolute = base + index
                    if absolute >= start and absolute + len(pattern) <= stop:
                        results.append(absolute)
                    search_from = index + 1
                carry = data[-overlap:] if overlap else b""
                position += len(block)
        return results

    def hex_dump(self, offset: int, length: int, width: int = 16) -> str:
        if width <= 0:
            raise ValueError("width must be greater than zero")
        data = self.read_at(offset, length)
        lines: list[str] = []
        for relative in range(0, len(data), width):
            chunk = data[relative:relative + width]
            hexadecimal = " ".join(f"{byte:02X}" for byte in chunk)
            printable = "".join(
                chr(byte) if 32 <= byte <= 126 else "." for byte in chunk
            )
            lines.append(
                f"{offset + relative:08X}  "
                f"{hexadecimal:<{width * 3 - 1}}  {printable}"
            )
        return "\n".join(lines)

    @staticmethod
    def _validate_non_negative(name: str, value: int) -> None:
        if value < 0:
            raise ValueError(f"{name} must not be negative")

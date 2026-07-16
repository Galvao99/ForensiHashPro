from dataclasses import dataclass, field

from app.binary.binary_reader import BinaryReader
from app.models.binary_string import BinaryString


@dataclass(slots=True)
class _Run:
    offset: int | None = None
    raw: bytearray = field(default_factory=bytearray)
    characters: list[str] = field(default_factory=list)

    def clear(self) -> None:
        self.offset = None
        self.raw.clear()
        self.characters.clear()


class BinaryStringExtractor:
    """Streaming extraction of conservative printable strings."""

    DEFAULT_MAXIMUM_STRING_BYTES = 1024 * 1024

    def __init__(
        self,
        minimum_length: int = 4,
        maximum_results: int = 1000,
        chunk_size: int = 64 * 1024,
        maximum_string_bytes: int = DEFAULT_MAXIMUM_STRING_BYTES,
    ) -> None:
        if minimum_length <= 0:
            raise ValueError("minimum_length must be greater than zero")
        if maximum_results <= 0:
            raise ValueError("maximum_results must be greater than zero")
        if chunk_size <= 0:
            raise ValueError("chunk_size must be greater than zero")
        if maximum_string_bytes <= 0:
            raise ValueError("maximum_string_bytes must be greater than zero")
        self.minimum_length = minimum_length
        self.maximum_results = maximum_results
        self.chunk_size = chunk_size
        self.maximum_string_bytes = maximum_string_bytes

    def extract(self, reader: BinaryReader) -> list[BinaryString]:
        results: list[BinaryString] = []
        ascii_run = _Run()
        utf_runs = {
            ("utf-16-le", parity): _Run()
            for parity in (0, 1)
        } | {
            ("utf-16-be", parity): _Run()
            for parity in (0, 1)
        }
        previous_byte: int | None = None

        for chunk_offset, chunk in reader.iter_chunks(self.chunk_size):
            for index, byte in enumerate(chunk):
                absolute = chunk_offset + index
                if self._is_ascii_printable(byte):
                    self._append_ascii(ascii_run, byte, absolute, results)
                else:
                    self._flush(ascii_run, "ascii", results)
                if len(results) >= self.maximum_results:
                    return sorted(results, key=lambda item: item.offset)

            for index, byte in enumerate(chunk):
                absolute = chunk_offset + index
                if previous_byte is not None:
                    pair_offset = absolute - 1
                    parity = pair_offset % 2
                    pair = bytes((previous_byte, byte))
                    # Each parity is an independent UTF-16 code-unit stream.
                    if pair_offset % 2 == parity:
                        for encoding in ("utf-16-le", "utf-16-be"):
                            run = utf_runs[(encoding, parity)]
                            try:
                                character = pair.decode(encoding)
                            except UnicodeDecodeError:
                                self._flush(run, encoding, results)
                                continue
                            if self._is_utf16_candidate(pair, encoding, character):
                                self._append_utf(
                                    run, pair, character, pair_offset, encoding, results
                                )
                            else:
                                self._flush(run, encoding, results)
                previous_byte = byte
            if len(results) >= self.maximum_results:
                return sorted(results, key=lambda item: item.offset)

        self._flush(ascii_run, "ascii", results)
        for (encoding, _), run in utf_runs.items():
            self._flush(run, encoding, results)
        return sorted(results, key=lambda item: item.offset)[:self.maximum_results]

    def _append_ascii(
        self, run: _Run, byte: int, offset: int, results: list[BinaryString]
    ) -> None:
        if run.offset is None:
            run.offset = offset
        run.raw.append(byte)
        run.characters.append(chr(byte))
        if len(run.raw) >= self.maximum_string_bytes:
            self._flush(run, "ascii", results)

    def _append_utf(
        self,
        run: _Run,
        pair: bytes,
        character: str,
        offset: int,
        encoding: str,
        results: list[BinaryString],
    ) -> None:
        if run.offset is None:
            run.offset = offset
        run.raw.extend(pair)
        run.characters.append(character)
        if len(run.raw) >= self.maximum_string_bytes:
            self._flush(run, encoding, results)

    def _flush(
        self, run: _Run, encoding: str, results: list[BinaryString]
    ) -> None:
        if encoding.startswith("utf-16") and run.offset is not None:
            ascii_end = max(
                (
                    item.offset + item.length
                    for item in results
                    if item.encoding == "ascii"
                    and item.offset < run.offset + len(run.raw)
                    and item.offset + item.length > run.offset
                ),
                default=run.offset,
            )
            trim = min(
                len(run.raw),
                max(0, ((ascii_end - run.offset + 1) // 2) * 2),
            )
            if trim:
                run.offset += trim
                del run.raw[:trim]
                del run.characters[:trim // 2]
        if (
            run.offset is not None
            and len(run.characters) >= self.minimum_length
            and len(results) < self.maximum_results
            and not (
                encoding.startswith("utf-16")
                and all(self._is_ascii_printable(byte) for byte in run.raw)
            )
        ):
            results.append(
                BinaryString(
                    offset=run.offset,
                    length=len(run.raw),
                    encoding=encoding,
                    value="".join(run.characters),
                )
            )
        run.clear()

    @staticmethod
    def _is_ascii_printable(byte: int) -> bool:
        return 32 <= byte <= 126 or byte in (9, 10, 13)

    @staticmethod
    def _is_unicode_printable(character: str) -> bool:
        return character.isprintable() or character in ("\t", "\n", "\r")

    @classmethod
    def _is_utf16_candidate(
        cls, pair: bytes, _encoding: str, character: str
    ) -> bool:
        return cls._is_unicode_printable(character)

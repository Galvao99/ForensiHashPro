from pathlib import Path

import pytest

from app.binary.binary_reader import BinaryReader
from app.binary.parsers.pdf_raw_parser import PdfRawParser


def parse(tmp_path: Path, content: bytes):
    path = tmp_path / "sample.bin"
    path.write_bytes(content)
    return PdfRawParser().analyze(BinaryReader(path))


def codes(result) -> set[str]:
    return {finding.code for finding in result.findings}


def test_minimal_pdf_and_single_eof(tmp_path: Path) -> None:
    result = parse(tmp_path, b"%PDF-1.7\n%%EOF")
    assert result.version == "1.7"
    assert result.header_offset == 0
    assert result.eof_offsets == [9]
    assert result.bytes_after_last_eof == 0


def test_displaced_header(tmp_path: Path) -> None:
    result = parse(tmp_path, b"prefix\n%PDF-1.4\n%%EOF")
    assert result.header_offset == 7
    assert "pdf_header_displaced" in codes(result)


def test_two_objects_preserve_offsets_and_end_markers(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj\n2 3 obj\n(hi)\nendobj\n%%EOF"
    result = parse(tmp_path, content)
    assert [(item.object_number, item.generation_number) for item in result.objects] == [(1, 0), (2, 3)]
    assert all(item.end_offset is not None for item in result.objects)
    assert result.objects[0].start_offset == content.index(b"1 0 obj")


def test_object_without_endobj_is_reported(tmp_path: Path) -> None:
    result = parse(tmp_path, b"%PDF-1.7\n1 0 obj\n<<>>\n%%EOF")
    assert result.objects[0].end_offset is None
    assert "pdf_object_without_endobj" in codes(result)


@pytest.mark.parametrize(
    ("ending", "expected_code"),
    [(b"endstream\nendobj\n%%EOF", None), (b"endobj\n%%EOF", "pdf_stream_without_endstream")],
)
def test_stream_states(tmp_path: Path, ending: bytes, expected_code: str | None) -> None:
    content = b"%PDF-1.7\n1 0 obj\n<< /Length 3 >>\nstream\nabc\n" + ending
    result = parse(tmp_path, content)
    assert result.stream_count == 1
    assert result.objects[0].has_stream
    assert (expected_code in codes(result)) if expected_code else ("pdf_stream_without_endstream" not in codes(result))


def test_tokens_inside_stream_are_not_confirmed(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n1 0 obj\n<<>>\nstream\n9 0 obj /JS xref trailer %%EOF\nendstream\nendobj\n%%EOF"
    result = parse(tmp_path, content)
    assert len(result.objects) == 1
    assert not result.has_javascript
    assert result.xref_offsets == []
    assert result.trailer_offsets == []
    assert len(result.eof_offsets) == 1


def test_traditional_xref_trailer_and_valid_startxref(tmp_path: Path) -> None:
    content = b"%PDF-1.7\nxref\n0 1\n0000000000 65535 f\ntrailer\n<< /Size 1 >>\nstartxref\n9\n%%EOF"
    result = parse(tmp_path, content)
    assert result.xref_offsets == [content.index(b"xref")]
    assert result.trailer_offsets == [content.index(b"trailer")]
    assert result.startxrefs[0].declared_offset == 9


def test_xref_stream(tmp_path: Path) -> None:
    content = b"%PDF-1.7\n4 0 obj\n<< /Type /XRef /Length 1 >>\nstream\nx\nendstream\nendobj\n%%EOF"
    result = parse(tmp_path, content)
    assert result.xref_stream_offsets == [content.index(b"4 0 obj")]


@pytest.mark.parametrize(
    ("value", "code"),
    [(b"invalid", "pdf_startxref_invalid"), (b"999999", "pdf_startxref_out_of_bounds")],
)
def test_invalid_startxref(tmp_path: Path, value: bytes, code: str) -> None:
    result = parse(tmp_path, b"%PDF-1.7\nstartxref\n" + value + b"\n%%EOF")
    assert code in codes(result)


def test_multiple_eof_trailers_and_bytes_after_eof(tmp_path: Path) -> None:
    result = parse(tmp_path, b"%PDF-1.7\ntrailer\n%%EOF\ntrailer\n%%EOFextra")
    assert len(result.eof_offsets) == 2
    assert len(result.trailer_offsets) == 2
    assert result.bytes_after_last_eof == 5
    assert {"pdf_multiple_eof", "pdf_multiple_trailers", "pdf_bytes_after_eof"} <= codes(result)


@pytest.mark.parametrize(
    ("entry", "attribute", "finding"),
    [
        (b"/Prev 12", "prev_offsets", "pdf_prev_detected"),
        (b"/Encrypt 2 0 R", "encrypted", "pdf_encryption_detected"),
        (b"/JavaScript 2 0 R", "has_javascript", "pdf_javascript_detected"),
        (b"/JS (x)", "has_javascript", "pdf_javascript_detected"),
        (b"/EmbeddedFile", "has_embedded_files", "pdf_embedded_files_detected"),
        (b"/Filespec", "has_embedded_files", "pdf_embedded_files_detected"),
        (b"/OpenAction 2 0 R", "has_open_action", "pdf_automatic_actions_detected"),
        (b"/AA <<>>", "has_additional_actions", "pdf_automatic_actions_detected"),
        (b"/AcroForm 2 0 R", "has_acroform", "pdf_acroform_detected"),
        (b"/XFA 2 0 R", "has_xfa", "pdf_xfa_detected"),
    ],
)
def test_structural_names(tmp_path: Path, entry: bytes, attribute: str, finding: str) -> None:
    result = parse(tmp_path, b"%PDF-1.7\n1 0 obj\n<< " + entry + b" >>\nendobj\n%%EOF")
    assert getattr(result, attribute)
    assert finding in codes(result)


def test_non_pdf_returns_valid_result_with_neutral_findings(tmp_path: Path) -> None:
    result = parse(tmp_path, b"ordinary bytes")
    assert result.header_offset is None
    assert "pdf_header_absent" in codes(result)
    assert "pdf_eof_absent" in codes(result)


def test_malformed_pdf_does_not_raise(tmp_path: Path) -> None:
    result = parse(tmp_path, b"%PDF-x\x00\xff\n1 0 obj\nstream\nbroken")
    assert result.version is None
    assert result.objects
    assert result.findings

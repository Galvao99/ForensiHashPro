from pathlib import Path
from types import SimpleNamespace

from PySide6.QtWidgets import QApplication

from app.digital_signature.parsers import pdf_parser
from app.digital_signature.parsers.pdf_parser import PdfSignatureParser
from app.engines.digital_signature_engine import DigitalSignatureEngine
from app.engines.file_analyzer import FileAnalyzer
from app.engines.score_evaluators.signature_evaluator import (
    SignatureEvaluator,
)
from app.models import (
    DigitalSignatureResult,
    SignatureAnalysisStatus,
)
from app.rules.integrity_rule import IntegrityRule
from app.widgets.digital_signature_card import DigitalSignatureCard


def _reader_with(signatures):
    return SimpleNamespace(
        embedded_signatures=signatures,
    )


def _integrity(signature: DigitalSignatureResult):
    analyzer = FileAnalyzer(
        hash_engine=None,
        metadata_engine=None,
        findings_engine=None,
        magic_number_engine=None,
        digital_signature_engine=None,
        pdf_structure_engine=None,
    )
    structure = SimpleNamespace(
        header_valid=True,
        eof_valid=True,
        eof_count=1,
        encrypted=False,
        javascript_detected=False,
        embedded_files=False,
        xref_found=True,
        trailer_found=True,
        incremental_updates=0,
    )

    return analyzer._build_integrity_result(
        hashes=SimpleNamespace(sha256="hash"),
        magic_numbers=SimpleNamespace(extension_matches=True),
        digital_signature=signature,
        pdf_structure=structure,
    )


def test_pdf_without_signature_is_confirmed_absent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    file_path = tmp_path / "unsigned.pdf"
    file_path.write_bytes(b"%PDF-1.7")
    monkeypatch.setattr(
        pdf_parser,
        "PdfFileReader",
        lambda file: _reader_with([]),
    )

    result = PdfSignatureParser().analyze(file_path)
    integrity = _integrity(result)
    findings = IntegrityRule().apply(integrity)

    assert result.analysis_status == SignatureAnalysisStatus.ABSENT
    assert result.has_signature is False
    assert integrity.score == 95
    assert any(
        finding.title == "Assinatura digital não identificada"
        for finding in findings
    )


def test_pdf_with_signature_is_confirmed_present(
    tmp_path: Path,
    monkeypatch,
) -> None:
    file_path = tmp_path / "signed.pdf"
    file_path.write_bytes(b"%PDF-1.7")
    signature = SimpleNamespace(
        md_algorithm="sha256",
        self_reported_timestamp=None,
        signer_info=None,
        signed_data=None,
        sig_object=None,
        signer_cert=None,
    )
    monkeypatch.setattr(
        pdf_parser,
        "PdfFileReader",
        lambda file: _reader_with([signature]),
    )

    result = PdfSignatureParser().analyze(file_path)
    integrity = _integrity(result)

    assert result.analysis_status == SignatureAnalysisStatus.PRESENT
    assert result.has_signature is True
    assert result.signature_count == 1
    assert integrity.score == 100
    assert not any(
        finding.title == "Assinatura digital não identificada"
        for finding in IntegrityRule().apply(integrity)
    )


def test_invalid_pdf_reports_analysis_error(
    tmp_path: Path,
) -> None:
    file_path = tmp_path / "invalid.pdf"
    file_path.write_bytes(b"not a pdf")

    result = PdfSignatureParser().analyze(file_path)

    assert result.analysis_status == SignatureAnalysisStatus.ERROR
    assert result.has_signature is None
    assert result.error_code
    assert result.error_message
    assert result.technical_status == (
        "Não foi possível concluir a análise da assinatura digital."
    )


def test_simulated_parser_exception_is_diagnostic_and_not_absence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    file_path = tmp_path / "error.pdf"
    file_path.write_bytes(b"%PDF-1.7")

    def raise_parser_error(file):
        raise RuntimeError("simulated parser failure")

    monkeypatch.setattr(
        pdf_parser,
        "PdfFileReader",
        raise_parser_error,
    )

    result = PdfSignatureParser().analyze(file_path)
    integrity = _integrity(result)
    findings = IntegrityRule().apply(integrity)

    assert result.analysis_status == SignatureAnalysisStatus.ERROR
    assert result.has_signature is None
    assert result.error_code == "RuntimeError"
    assert result.error_message == "simulated parser failure"
    assert integrity.score == 100
    assert any(
        finding.title
        == "Não foi possível analisar a assinatura digital"
        for finding in findings
    )
    assert not any(
        finding.title == "Assinatura digital não identificada"
        for finding in findings
    )


def test_parser_diagnostics_are_not_exposed_in_card_or_finding(
    tmp_path: Path,
    monkeypatch,
) -> None:
    qt_app = QApplication.instance() or QApplication([])
    file_path = tmp_path / "error.pdf"
    file_path.write_bytes(b"%PDF-1.7")
    private_path = "C:/Users/private/OneDrive/internal.pdf"
    library_name = "pyhanko.internal.reader"
    technical_detail = "unexpected xref object 42"
    raw_error = f"{library_name}: {technical_detail} at {private_path}"

    def raise_parser_error(file):
        raise RuntimeError(raw_error)

    monkeypatch.setattr(
        pdf_parser,
        "PdfFileReader",
        raise_parser_error,
    )

    result = PdfSignatureParser().analyze(file_path)
    findings = IntegrityRule().apply(_integrity(result))
    card = DigitalSignatureCard()
    card.update_signature(result)
    assert qt_app is not None
    public_text = "\n".join(
        [card.content.text()]
        + [finding.description for finding in findings]
    )

    assert result.error_code == "RuntimeError"
    assert result.error_message == raw_error
    assert result.technical_status == (
        "Não foi possível concluir a análise da assinatura digital."
    )
    for private_value in (
        private_path,
        library_name,
        technical_detail,
        raw_error,
    ):
        assert private_value not in public_text


def test_not_applicable_and_unsupported_are_not_absence(
    tmp_path: Path,
) -> None:
    not_applicable = DigitalSignatureResult(
        has_signature=None,
        analysis_status=SignatureAnalysisStatus.NOT_APPLICABLE,
        technical_status="Análise não aplicável.",
    )
    file_path = tmp_path / "image.jpg"
    file_path.write_bytes(b"\xff\xd8\xff")
    unsupported = DigitalSignatureEngine().analyze(file_path)

    assert unsupported.analysis_status == SignatureAnalysisStatus.UNSUPPORTED
    assert unsupported.has_signature is None

    for result in (not_applicable, unsupported):
        integrity = _integrity(result)
        score_section = SignatureEvaluator().evaluate(
            SimpleNamespace(digital_signature=result)
        )

        assert integrity.digital_signature_present is None
        assert integrity.score == 100
        assert score_section.weight == 0
        assert not any(
            finding.title == "Assinatura digital não identificada"
            for finding in IntegrityRule().apply(integrity)
        )

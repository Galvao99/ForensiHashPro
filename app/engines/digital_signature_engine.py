from pathlib import Path

from app.digital_signature.parsers.pdf_parser import PdfSignatureParser
from app.models import DigitalSignatureResult


class DigitalSignatureEngine:
    """Seleciona o parser adequado para análise de assinatura digital."""

    def __init__(self) -> None:
        self.pdf_parser = PdfSignatureParser()

    def analyze(self, file_path: Path) -> DigitalSignatureResult:
        if file_path.suffix.lower() == ".pdf":
            return self.pdf_parser.analyze(file_path)

        return DigitalSignatureResult(
            has_signature=False,
            signature_count=0,
            technical_status=(
                "Formato ainda não suportado para análise de assinatura digital."
            ),
        )
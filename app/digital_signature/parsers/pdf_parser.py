from pathlib import Path

from pyhanko.pdf_utils.reader import PdfFileReader

from app.digital_signature.parsers.base_parser import BaseSignatureParser
from app.models import DigitalSignatureResult


class PdfSignatureParser(BaseSignatureParser):
    """Parser de assinaturas digitais em documentos PDF."""

    def analyze(self, file_path: Path) -> DigitalSignatureResult:
        try:
            with file_path.open("rb") as file:
                reader = PdfFileReader(file)
                signatures = list(reader.embedded_signatures)

            if not signatures:
                return DigitalSignatureResult(
                    has_signature=False,
                    signature_count=0,
                    technical_status=(
                        "Nenhuma assinatura digital incorporada foi identificada no PDF analisado."
                    ),
                )

            first_signature = signatures[0]
            signer_cert = getattr(first_signature, "signer_cert", None)

            signer = None
            issuer = None
            serial_number = None

            if signer_cert:
                signer = str(signer_cert.subject.human_friendly)
                issuer = str(signer_cert.issuer.human_friendly)
                serial_number = str(signer_cert.serial_number)

                valid_from = signer_cert["tbs_certificate"]["validity"]["not_before"].native
                valid_until = signer_cert["tbs_certificate"]["validity"]["not_after"].native
            else:
                valid_from = None
                valid_until = None

            return DigitalSignatureResult(
                has_signature=True,
                signature_count=len(signatures),
                signer=signer,
                issuer=issuer,
                serial_number=serial_number,
                valid_from=str(valid_from) if valid_from else None,
                valid_until=str(valid_until) if valid_until else None,
                technical_status=(
                    "Assinatura digital incorporada identificada no PDF. "
                    "A validação criptográfica completa ainda não foi realizada."
                ),
            )

        except Exception as error:
            return DigitalSignatureResult(
                has_signature=False,
                signature_count=0,
                technical_status=(
                    f"Não foi possível analisar assinaturas digitais neste PDF: {error}"
                ),
            )
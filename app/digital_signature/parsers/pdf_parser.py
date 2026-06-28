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
            
            # verificação de assinatura digital incorporada no PDF
            # Diferente de signing_time, que representa a data declarada da assinatura.

            print("\n========= DADOS DIRETOS =========")
            print("md_algorithm:", getattr(first_signature, "md_algorithm", None))
            print(
                "self_reported_timestamp:",
                getattr(first_signature, "self_reported_timestamp", None),
            )

            print("\n========= signer_info =========")
            signer_info = getattr(first_signature, "signer_info", None)
            print(type(signer_info))
            print(dir(signer_info))

            print("\n========= signed_data =========")
            signed_data = getattr(first_signature, "signed_data", None)
            print(type(signed_data))
            print(dir(signed_data))

            print("\n========= sig_object =========")
            sig_object = getattr(first_signature, "sig_object", None)
            print(type(sig_object))
            print(dir(sig_object))

            signer_cert = getattr(first_signature, "signer_cert", None)

            signer = None
            issuer = None
            serial_number = None
            valid_from = None
            valid_until = None

            if signer_cert:
                signer = str(signer_cert.subject.human_friendly)
                issuer = str(signer_cert.issuer.human_friendly)
                serial_number = str(signer_cert.serial_number)

                valid_from = signer_cert["tbs_certificate"]["validity"]["not_before"].native
                valid_until = signer_cert["tbs_certificate"]["validity"]["not_after"].native

            return DigitalSignatureResult(
                has_signature=True,
                signature_count=len(signatures),
                signer=signer,
                issuer=issuer,
                serial_number=serial_number,
                algorithm=str(getattr(first_signature, "md_algorithm", None)),
                signing_time=str(getattr(first_signature, "self_reported_timestamp", None)),
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
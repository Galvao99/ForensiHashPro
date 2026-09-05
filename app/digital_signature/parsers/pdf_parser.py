from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
from typing import Any

from pyhanko.pdf_utils.reader import PdfFileReader

from app.digital_signature.parsers.base_parser import BaseSignatureParser
from app.models import (
    CertificateIdentity,
    DigitalSignatureResult,
    SignatureAnalysisStatus,
    SignatureLocator,
    SignatureParseIssue,
    SignatureRecord,
)


class PdfSignatureParser(BaseSignatureParser):
    """Extract every embedded PDF signature without performing validation."""

    def analyze(self, file_path: Path) -> DigitalSignatureResult:
        try:
            with file_path.open("rb") as file:
                reader = PdfFileReader(file)
                embedded = list(reader.embedded_signatures)
                if not embedded:
                    return DigitalSignatureResult(
                        has_signature=False,
                        signature_count=0,
                        analysis_status=SignatureAnalysisStatus.ABSENT,
                        technical_status=(
                            "Nenhuma assinatura digital incorporada foi identificada no PDF analisado."
                        ),
                    )
                records, issues = self._records(file_path, embedded)
        except Exception as error:
            return DigitalSignatureResult(
                has_signature=None,
                signature_count=0,
                analysis_status=SignatureAnalysisStatus.ERROR,
                error_code=type(error).__name__,
                error_message=str(error),
                technical_status="Não foi possível concluir a análise da assinatura digital.",
            )

        technical_status = (
            "Assinaturas digitais incorporadas identificadas no PDF. "
            "A validação criptográfica completa não foi realizada."
        )
        if issues:
            technical_status += " Uma ou mais assinaturas tiveram extração parcial."
        return DigitalSignatureResult(
            has_signature=True,
            signature_count=len(embedded),
            analysis_status=SignatureAnalysisStatus.PRESENT,
            signatures=records,
            signature_errors=issues,
            technical_status=technical_status,
        )

    def _records(
        self, file_path: Path, embedded: list[Any],
    ) -> tuple[tuple[SignatureRecord, ...], tuple[SignatureParseIssue, ...]]:
        records: list[SignatureRecord] = []
        issues: list[SignatureParseIssue] = []
        for index, signature in enumerate(embedded):
            locator = self._locator(signature, index)
            try:
                records.append(self._record(file_path, signature, locator))
            except Exception as error:
                issues.append(SignatureParseIssue(
                    embedded_index=index,
                    locator=locator.canonical,
                    code="signature_record_extraction_failed",
                    error_type=type(error).__name__,
                    message="Não foi possível extrair todos os campos desta assinatura.",
                ))
        records.sort(key=lambda item: (
            item.locator.signed_revision
            if item.locator.signed_revision is not None else 2**31,
            item.locator.canonical,
            item.signature_id,
        ))
        issues.sort(key=lambda item: (item.embedded_index, item.locator, item.code))
        return tuple(records), tuple(issues)

    def _record(
        self, file_path: Path, signature: Any, locator: SignatureLocator,
    ) -> SignatureRecord:
        certificate = self._certificate(getattr(signature, "signer_cert", None))
        signing_time = getattr(signature, "self_reported_timestamp", None)
        return SignatureRecord(
            signature_id=self._signature_id(file_path, locator),
            locator=locator,
            certificate=certificate,
            algorithm=self._optional_text(getattr(signature, "md_algorithm", None)),
            signing_time=self._optional_text(signing_time),
            trusted_timestamp=None,
            signature_type=self._optional_text(getattr(signature, "sig_object_type", None)),
        )

    @staticmethod
    def _certificate(certificate: Any) -> CertificateIdentity | None:
        if certificate is None:
            return None
        der = certificate.dump()
        fingerprint = sha256(der).hexdigest()
        validity = certificate["tbs_certificate"]["validity"]
        valid_from = validity["not_before"].native
        valid_until = validity["not_after"].native
        return CertificateIdentity(
            certificate_id=f"certificate:sha256:{fingerprint}",
            fingerprint_sha256=fingerprint,
            subject=str(certificate.subject.human_friendly),
            issuer=str(certificate.issuer.human_friendly),
            serial_number=str(certificate.serial_number),
            valid_from=str(valid_from) if valid_from is not None else None,
            valid_until=str(valid_until) if valid_until is not None else None,
        )

    @staticmethod
    def _locator(signature: Any, index: int) -> SignatureLocator:
        field_name = PdfSignatureParser._safe_text(signature, "field_name")
        signed_revision = PdfSignatureParser._safe_int(signature, "signed_revision")
        byte_range = PdfSignatureParser._safe_int_tuple(signature, "byte_range")
        object_number, generation = PdfSignatureParser._object_reference(signature)
        return SignatureLocator(
            field_name=field_name,
            object_number=object_number,
            object_generation=generation,
            signed_revision=signed_revision,
            byte_range=byte_range,
            embedded_index=index,
        )

    @staticmethod
    def _object_reference(signature: Any) -> tuple[int | None, int | None]:
        try:
            reference = signature.sig_field.raw_get("/V").reference
            return int(reference.idnum), int(reference.generation)
        except (AttributeError, KeyError, TypeError, ValueError):
            return None, None

    @staticmethod
    def _signature_id(file_path: Path, locator: SignatureLocator) -> str:
        artifact = os.path.normcase(os.path.abspath(os.fspath(file_path)))
        payload = json.dumps(
            [artifact, locator.canonical], ensure_ascii=False,
            separators=(",", ":"), sort_keys=True,
        )
        return sha256(f"forensihash:pdf-signature:v1:{payload}".encode("utf-8")).hexdigest()

    @staticmethod
    def _safe_text(value: Any, attribute: str) -> str | None:
        try:
            return PdfSignatureParser._optional_text(getattr(value, attribute, None))
        except Exception:
            return None

    @staticmethod
    def _safe_int(value: Any, attribute: str) -> int | None:
        try:
            raw = getattr(value, attribute, None)
            return int(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int_tuple(value: Any, attribute: str) -> tuple[int, ...]:
        try:
            return tuple(int(item) for item in (getattr(value, attribute, ()) or ()))
        except (TypeError, ValueError):
            return ()

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text if text and text.lower() != "none" else None

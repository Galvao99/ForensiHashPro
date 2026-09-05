from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace

from app.correlation.case_result import EpistemicState
from app.correlation.v2 import (
    AnalysisResultCorrelationProvider,
    CaseEvidenceIndex,
    EntityType,
    EvidenceGraphCorrelationEngine,
    RelationType,
    SignatureCorrelationProvider,
    source_file_identity,
)
from app.correlation.v2.pipeline import SigningTimeCertificateValidityRule
from app.digital_signature.parsers import pdf_parser
from app.digital_signature.parsers.pdf_parser import PdfSignatureParser
from app.models import (
    CertificateIdentity,
    DigitalSignatureResult,
    SignatureLocator,
    SignatureRecord,
    SignatureValidationStatus,
)


class NativeValue:
    def __init__(self, native):
        self.native = native


class FakeCertificate:
    def __init__(self, der: bytes, name: str, serial: int = 7):
        self._der = der
        self.subject = SimpleNamespace(human_friendly=f"CN={name}")
        self.issuer = SimpleNamespace(human_friendly="CN=Issuer")
        self.serial_number = serial
        self._validity = {
            "not_before": NativeValue(datetime(2026, 1, 1, tzinfo=timezone.utc)),
            "not_after": NativeValue(datetime(2027, 1, 1, tzinfo=timezone.utc)),
        }

    def dump(self) -> bytes:
        return self._der

    def __getitem__(self, key):
        if key == "tbs_certificate":
            return {"validity": self._validity}
        raise KeyError(key)


class FakeReference:
    def __init__(self, number: int, generation: int = 0):
        self.idnum = number
        self.generation = generation


class FakeField:
    def __init__(self, number: int):
        self._reference = FakeReference(number)

    def raw_get(self, key: str):
        assert key == "/V"
        return SimpleNamespace(reference=self._reference)


def fake_signature(
    field: str, object_number: int, revision: int, certificate: FakeCertificate,
    signing_time: datetime,
):
    return SimpleNamespace(
        field_name=field,
        sig_field=FakeField(object_number),
        signed_revision=revision,
        byte_range=(0, 100 * revision, 200 * revision, 300 * revision),
        signer_cert=certificate,
        self_reported_timestamp=signing_time,
        md_algorithm="sha256",
        sig_object_type="/Sig",
    )


def parse(tmp_path: Path, monkeypatch, signatures):
    path = tmp_path / "signed.pdf"
    path.write_bytes(b"%PDF-1.7")
    monkeypatch.setattr(
        pdf_parser, "PdfFileReader",
        lambda stream: SimpleNamespace(embedded_signatures=signatures),
    )
    return path, PdfSignatureParser().analyze(path)


def test_one_signature_produces_one_record_and_legacy_projection(tmp_path, monkeypatch) -> None:
    certificate = FakeCertificate(b"certificate-a", "Signer A")
    path, result = parse(tmp_path, monkeypatch, [fake_signature(
        "Signature1", 12, 1, certificate,
        datetime(2026, 6, 1, tzinfo=timezone.utc),
    )])
    assert path.exists()
    assert result.signature_count == len(result.signatures) == 1
    record = result.signatures[0]
    assert result.signer == record.certificate.subject == "CN=Signer A"
    assert result.issuer == record.certificate.issuer == "CN=Issuer"
    assert result.serial_number == record.certificate.serial_number == "7"
    assert result.algorithm == record.algorithm == "sha256"
    assert result.signing_time == record.signing_time
    assert result.valid_from == record.certificate.valid_from
    assert result.valid_until == record.certificate.valid_until
    assert result.validation_status is SignatureValidationStatus.NOT_PERFORMED


def test_three_signatures_have_independent_unique_structural_records(tmp_path, monkeypatch) -> None:
    signatures = [
        fake_signature(
            f"Signature{index}", 10 + index, index,
            FakeCertificate(f"certificate-{index}".encode(), f"Signer {index}", index),
            datetime(2026, index, 1, tzinfo=timezone.utc),
        )
        for index in (1, 2, 3)
    ]
    _, result = parse(tmp_path, monkeypatch, signatures)
    assert result.signature_count == len(result.signatures) == 3
    assert len({item.signature_id for item in result.signatures}) == 3
    assert [item.locator.field_name for item in result.signatures] == [
        "Signature1", "Signature2", "Signature3",
    ]
    assert [item.locator.object_number for item in result.signatures] == [11, 12, 13]
    assert all(item.locator.byte_range for item in result.signatures)


def test_signature_and_certificate_ids_are_deterministic(tmp_path, monkeypatch) -> None:
    certificate = FakeCertificate(b"same-der", "Signer")
    signature = fake_signature(
        "Signature1", 42, 3, certificate,
        datetime(2026, 6, 1, tzinfo=timezone.utc),
    )
    _, first = parse(tmp_path, monkeypatch, [signature])
    _, second = parse(tmp_path, monkeypatch, [signature])
    assert first.signatures[0].signature_id == second.signatures[0].signature_id
    assert first.signatures[0].certificate.certificate_id == second.signatures[0].certificate.certificate_id
    assert first.signatures[0].certificate.fingerprint_sha256 == sha256(b"same-der").hexdigest()


def test_same_certificate_reused_keeps_identity_without_collapsing_signatures(tmp_path, monkeypatch) -> None:
    certificate = FakeCertificate(b"shared-certificate", "Signer")
    signatures = [
        fake_signature("Signature1", 10, 1, certificate, datetime(2026, 4, 1, tzinfo=timezone.utc)),
        fake_signature("Signature2", 20, 2, certificate, datetime(2026, 5, 1, tzinfo=timezone.utc)),
    ]
    _, result = parse(tmp_path, monkeypatch, signatures)
    assert len({item.signature_id for item in result.signatures}) == 2
    assert len({item.certificate.certificate_id for item in result.signatures}) == 1


class BrokenSignature:
    field_name = "Broken"
    sig_field = FakeField(20)
    signed_revision = 2
    byte_range = (0, 1, 2, 3)
    md_algorithm = "sha256"
    sig_object_type = "/Sig"

    @property
    def signer_cert(self):
        raise ValueError("private parser detail C:/secret/file.pdf")


def test_malformed_signature_does_not_erase_valid_siblings(tmp_path, monkeypatch) -> None:
    valid_a = fake_signature(
        "Signature1", 10, 1, FakeCertificate(b"a", "A"),
        datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    valid_c = fake_signature(
        "Signature3", 30, 3, FakeCertificate(b"c", "C"),
        datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    _, result = parse(tmp_path, monkeypatch, [valid_a, BrokenSignature(), valid_c])
    assert result.signature_count == 3
    assert [item.locator.field_name for item in result.signatures] == ["Signature1", "Signature3"]
    assert len(result.signature_errors) == 1
    issue = result.signature_errors[0]
    assert issue.error_type == "ValueError"
    assert "secret" not in issue.message and "private parser detail" not in issue.message
    assert result.validation_status is SignatureValidationStatus.NOT_PERFORMED


def record(
    signature_id: str, locator: str, certificate_id: str,
    signing: str, lower: str, upper: str,
) -> SignatureRecord:
    return SignatureRecord(
        signature_id=signature_id,
        locator=SignatureLocator(field_name=locator, signed_revision=int(locator[-1])),
        certificate=CertificateIdentity(
            certificate_id=certificate_id,
            fingerprint_sha256=certificate_id.rsplit(":", 1)[-1],
            valid_from=lower, valid_until=upper,
        ),
        signing_time=signing,
    )


def analysis_result(path: Path, records: tuple[SignatureRecord, ...]):
    return SimpleNamespace(
        file_info=SimpleNamespace(name=path.name, path=path),
        hashes=SimpleNamespace(sha256="f" * 64, md5=""), evidence_source=None,
        digital_signature=DigitalSignatureResult(
            has_signature=True, signature_count=len(records), signatures=records,
        ),
        resolved_entities=[], processing_steps=[], metadata=SimpleNamespace(raw={}),
        json_analysis=None, timeline_events=[],
    )


def test_provider_emits_independent_graph_bindings_and_rule_results(tmp_path: Path) -> None:
    records = (
        record(
            "signature-a", "Signature1", "certificate:sha256:" + "a" * 64,
            "2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
        ),
        record(
            "signature-b", "Signature2", "certificate:sha256:" + "b" * 64,
            "2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z",
        ),
    )
    result = analysis_result(tmp_path / "signed.pdf", records)
    batch = AnalysisResultCorrelationProvider().provide_case([result])
    graph = EvidenceGraphCorrelationEngine().correlate(
        batch.candidates,
        signature_temporal_bindings=batch.signature_temporal_bindings,
    )
    index = CaseEvidenceIndex(graph)
    source = source_file_identity(
        display_name=result.file_info.name, path=result.file_info.path,
        sha256=result.hashes.sha256,
    )
    assert index.signatures_for_artifact(source.stable_id) == ("signature-a", "signature-b")
    assert index.certificates_for_signature("signature-a") == (
        "certificate:sha256:" + "a" * 64,
    )
    assert index.certificates_for_signature("signature-b") == (
        "certificate:sha256:" + "b" * 64,
    )
    assert {item.semantic_role for item in index.for_signature("signature-a")} == {
        "signer_declared_signing_time", "certificate_not_before", "certificate_not_after",
    }
    findings = SigningTimeCertificateValidityRule().evaluate(index).findings
    assert {
        (item.metadata["signature_id"], item.epistemic_state)
        for item in findings
    } == {
        ("signature-a", EpistemicState.MATCH),
        ("signature-b", EpistemicState.MISMATCH),
    }
    assert not any(
        item.entity_type is EntityType.SHA256
        and item.normalized_value in {"a" * 64, "b" * 64}
        for item in graph.entities
    )


def test_collection_order_and_graph_relation_ids_are_deterministic(tmp_path: Path) -> None:
    records = (
        record("signature-a", "Signature1", "certificate:sha256:" + "a" * 64, "2026-06-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
        record("signature-b", "Signature2", "certificate:sha256:" + "b" * 64, "2026-07-01T00:00:00Z", "2026-01-01T00:00:00Z", "2027-01-01T00:00:00Z"),
    )
    outputs = []
    for current in (records, records):
        batch = AnalysisResultCorrelationProvider().provide_case([
            analysis_result(tmp_path / "signed.pdf", current)
        ])
        graph = EvidenceGraphCorrelationEngine().correlate(
            batch.candidates,
            signature_temporal_bindings=batch.signature_temporal_bindings,
        )
        outputs.append(tuple(item.stable_id for item in graph.relations))
    assert outputs[0] == outputs[1]
    assert RelationType.ARTIFACT_CONTAINS_SIGNATURE in {
        item.relation_type for item in graph.relations
    }

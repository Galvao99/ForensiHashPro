from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from zipfile import ZipFile

import fitz
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web.backend.app.api.routes import get_db
from web.backend.app.database import Base
from web.backend.app.main import app
from web.backend.app.models import StoredAnalysis, User
from web.backend.app.services.ddna_snapshot import DdnaSnapshotService


@pytest.fixture
def platform():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), factory
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _contract(analysis_id: str = "analysis-snapshot", *, profile: str = "free") -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "analysis_id": analysis_id,
        "evidence_id": "evidence-snapshot",
        "state": "completed",
        "file": {
            "name": "contrato.pdf",
            "size_bytes": 862208,
            "mime_type": "application/pdf",
        },
        "hashes": {
            "md5": "b" * 32,
            "sha1": "c" * 40,
            "sha256": "a" * 64,
        },
        "declared_type": ".pdf",
        "detected_type": "PDF",
        "metadata": {
            "CreateDate": "2024:01:02 03:04:05-03:00",
            "ModifyDate": "2024:01:03 04:05:06-03:00",
            "Producer": "Synthetic Producer",
        },
        "technical_structure": {
            "pdf": {
                "pdf_version": "1.7",
                "object_count": 183,
                "stream_count": 42,
                "xref_found": True,
                "trailer_found": True,
                "eof_count": 2,
                "incremental_updates": True,
            }
        },
        "signatures": [],
        "findings": [{
            "title": "Revisoes incrementais observadas",
            "statement": "Foram observados marcadores estruturais de revisao.",
            "rule_id": "legacy.integrity",
            "severity": "warning",
            "evidence_refs": ["evidence-snapshot"],
            "confidence": 0.8,
        }],
        "limitations": [{
            "code": "profile_scope",
            "message": "Resultados limitados as capacidades executadas.",
        }],
        "errors": [],
        "processing_steps": [
            {"code": "metadata_extraction", "status": "success", "finished_at": "2026-08-16T12:00:01+00:00"},
            {"code": "ocr", "component": "ocr", "status": "skipped", "safe_details": {"reason": "capability_not_enabled", "capability": "ocr"}},
        ],
        "facts": [{"kind": "metadata", "source": "metadata_engine"}],
        "execution": {
            "analysis_profile": profile,
            "runtime": "python",
            "started_at": "2026-08-16T12:00:00+00:00",
            "finished_at": "2026-08-16T12:00:02+00:00",
        },
    }


def _pdf_text(pdf_bytes: bytes) -> str:
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return "\n".join(page.get_text() for page in document)
    finally:
        document.close()


def test_snapshot_pdf_contains_real_analysis_and_required_disclaimer() -> None:
    package = DdnaSnapshotService().generate(
        _contract(),
        generated_at=datetime(2026, 8, 16, 15, 30, tzinfo=timezone.utc),
        snapshot_id="snapshot-fixed",
    )
    text = _pdf_text(package.pdf_bytes)
    normalized_text = " ".join(text.split())

    for expected in (
        "FORENSIHASH",
        "DDNA SNAPSHOT",
        "ARQEN",
        "contrato.pdf",
        "a" * 64,
        "Synthetic Producer",
        "183",
        "Revisoes incrementais observadas",
        "Resultados limitados as capacidades executadas.",
        "0.1.0",
        "2026-08-16T15:30:00+00:00",
        "não representa cadeia de custódia original",
        "não constitui DDNA Manifest",
        "não é assinado digitalmente",
    ):
        assert expected in normalized_text
    assert "autenticidade comprovada" not in text.lower()
    assert "certificado" not in text.lower()
    assert "HASH DO SNAPSHOT" in text
    assert "Consulte o arquivo .sha256 acompanhante." in text


def test_checksum_is_over_final_pdf_and_detects_one_byte_change() -> None:
    package = DdnaSnapshotService().generate(
        _contract(),
        generated_at=datetime(2026, 8, 16, 15, 30, tzinfo=timezone.utc),
        snapshot_id="snapshot-fixed",
    )
    exported = package.checksum_bytes.decode("ascii").strip().split("=", 1)[1]
    assert exported == sha256(package.pdf_bytes).hexdigest()
    changed = bytearray(package.pdf_bytes)
    changed[-1] ^= 1
    assert sha256(changed).hexdigest() != exported

    with ZipFile(BytesIO(package.zip_bytes)) as archive:
        names = archive.namelist()
        assert names == [
            "forensihash_ddna_snapshot_analysis-snapshot.pdf",
            "forensihash_ddna_snapshot_analysis-snapshot.sha256",
        ]
        assert archive.read(names[0]) == package.pdf_bytes
        assert archive.read(names[1]) == package.checksum_bytes


def test_free_snapshot_does_not_present_unexecuted_advanced_results() -> None:
    text = _pdf_text(DdnaSnapshotService().generate(_contract()).pdf_bytes)

    assert "OCR VAZIO" not in text
    assert "ENTIDADES VAZIAS" not in text
    assert "TIMELINE AVANCADA" not in text
    assert "CORRELACAO VAZIA" not in text
    assert "BIOMETRIA VAZIA" not in text
    assert "ocr: análise não executada neste perfil" in text


def _register(client: TestClient, email: str) -> dict[str, object]:
    return client.post("/api/v1/auth/register", json={
        "name": "Pessoa Snapshot",
        "email": email,
        "password": "correct-horse-42",
        "accept_terms": True,
        "accept_privacy": True,
    }).json()


def test_snapshot_endpoint_requires_auth_csrf_and_ownership(platform) -> None:
    client, factory = platform
    assert client.post("/api/v1/analyses/missing/ddna-snapshot").status_code == 401
    owner_auth = _register(client, "owner-snapshot@example.test")
    with factory() as db:
        owner = db.scalar(select(User).where(User.email == "owner-snapshot@example.test"))
        db.add(StoredAnalysis(
            id="owned-analysis",
            user_id=owner.id,
            filename="contrato.pdf",
            detected_type="PDF",
            sha256="a" * 64,
            status="completed",
            retention_mode="RESULT_ONLY",
            result_json=_contract("owned-analysis"),
        ))
        db.commit()

    without_csrf = client.post("/api/v1/analyses/owned-analysis/ddna-snapshot")
    assert without_csrf.status_code == 403
    response = client.post(
        "/api/v1/analyses/owned-analysis/ddna-snapshot",
        headers={"X-CSRF-Token": owner_auth["csrf_token"]},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/zip"
    assert "forensihash_ddna_snapshot_owned-analysis.zip" in response.headers["content-disposition"]

    client.cookies.clear()
    other_auth = _register(client, "other-snapshot@example.test")
    foreign = client.post(
        "/api/v1/analyses/owned-analysis/ddna-snapshot",
        headers={"X-CSRF-Token": other_auth["csrf_token"]},
    )
    assert foreign.status_code == 404
    assert foreign.json()["error"]["code"] == "analysis_not_found"

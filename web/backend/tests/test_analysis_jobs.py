from __future__ import annotations

from pathlib import Path
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import AnalysisContract, AnalysisState
from app.evidence import EvidenceSizeLimitError
from web.backend.app.api.routes import get_analysis_job_executor, get_upload_storage, get_web_analysis_service
from web.backend.app.main import app
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, StoredAnalysis
from web.backend.app.database import Base, get_db
from web.backend.app.services import AnalysisJobExecutor, UploadStorage


class WakeOnly:
    def wake(self) -> None:
        pass


@pytest.fixture
def platform(tmp_path: Path):
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    def database_override():
        with factory() as session:
            yield session
    app.dependency_overrides[get_db] = database_override
    try:
        yield TestClient(app), factory, tmp_path
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def contract(state: AnalysisState = AnalysisState.COMPLETED, analysis_id: str = "job-analysis") -> AnalysisContract:
    return AnalysisContract(schema_version="1.0.0", analysis_id=analysis_id, evidence_id="evidence",
        state=state, file={"name": "sample.txt", "size_bytes": 4}, hashes={"sha256": "a" * 64},
        declared_type=".txt", detected_type="TEXT")


def create_job(client, csrf: str, *, retention: str = "PRIVATE"):
    return client.post("/api/v1/analysis-jobs", files={"file": ("../../sample.txt", b"data")},
        data={"private_session": str(retention == "PRIVATE").lower(), "retention_mode": retention},
        headers={"X-CSRF-Token": csrf})


def test_job_creation_returns_202_without_running_coordinator(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Job User", "email": "job@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    called = False
    class Service:
        def analyze(self, *_args, **_kwargs):
            nonlocal called
            called = True
            return contract()
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    app.dependency_overrides[get_web_analysis_service] = Service

    response = create_job(client, auth["csrf_token"])

    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED"
    assert called is False
    with factory() as db:
        job = db.get(AnalysisJob, response.json()["job_id"])
        assert job and job.status == "QUEUED" and Path(job.staging_path).is_file()
        assert job.original_filename == "sample.txt"


def test_private_job_lifecycle_result_and_cleanup(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Job User", "email": "job2@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    created = create_job(client, auth["csrf_token"])
    job_id = created.json()["job_id"]
    assert client.get(f"/api/v1/analysis-jobs/{job_id}/result").status_code == 409

    observed: list[str] = []
    class Service:
        def analyze(self, path, **_kwargs):
            with factory() as db:
                observed.append(db.get(AnalysisJob, job_id).status)
            assert Path(path).is_file()
            return contract()
    executor = AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Service)
    assert executor.process_next() is True

    assert observed == ["PROCESSING"]
    status = client.get(f"/api/v1/analysis-jobs/{job_id}").json()
    assert status["status"] == "SUCCESS" and status["analysis_id"] == "job-analysis"
    assert client.get(f"/api/v1/analysis-jobs/{job_id}/result").json()["schema_version"] == "1.0.0"
    assert list(storage.root.iterdir()) == []
    with factory() as db:
        assert db.scalar(select(StoredAnalysis)) is None
        job = db.get(AnalysisJob, job_id)
        job.result_expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    executor.process_next()
    assert client.get(f"/api/v1/analysis-jobs/{job_id}/result").status_code == 410


def test_result_only_partial_is_persisted_and_jobs_are_independent(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Job User", "email": "job3@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    first = create_job(client, auth["csrf_token"], retention="RESULT_ONLY").json()["job_id"]
    second = create_job(client, auth["csrf_token"], retention="RESULT_ONLY").json()["job_id"]
    assert first != second
    sequence = iter([contract(AnalysisState.PARTIAL, "partial-analysis"), contract(AnalysisState.COMPLETED, "second-analysis")])
    class Service:
        def analyze(self, *_args, **_kwargs): return next(sequence)
    executor = AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Service)
    executor.process_next()
    executor.process_next()

    assert client.get(f"/api/v1/analysis-jobs/{first}").json()["status"] == "PARTIAL"
    assert client.get(f"/api/v1/analysis-jobs/{second}").json()["status"] == "SUCCESS"
    with factory() as db:
        assert {item.id for item in db.scalars(select(StoredAnalysis))} == {"partial-analysis", "second-analysis"}


def test_failure_cleanup_recovery_and_authorization(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Owner", "email": "owner@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    job_id = create_job(client, auth["csrf_token"]).json()["job_id"]
    class Failure:
        def analyze(self, *_args, **_kwargs): raise RuntimeError("private stack detail")
    AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Failure).process_next()
    failed = client.get(f"/api/v1/analysis-jobs/{job_id}").json()
    assert failed["status"] == "FAILED" and failed["error_code"] == "processing_failed"
    assert "private" not in failed["safe_error_message"].lower()
    assert list(storage.root.iterdir()) == []

    client.cookies.clear()
    client.post("/api/v1/auth/register", json={"name": "Other", "email": "other-job@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True})
    assert client.get(f"/api/v1/analysis-jobs/{job_id}").status_code == 404

    with factory() as db:
        owner_job = db.get(AnalysisJob, job_id)
        owner_job.status = AnalysisJobStatus.PROCESSING.value
        owner_job.staging_path = str(tmp_path / "missing.bin")
        db.commit()
    AnalysisJobExecutor(factory, storage=storage).recover()
    with factory() as db:
        recovered = db.get(AnalysisJob, job_id)
        assert recovered.status == "FAILED" and recovered.error_code == "staging_lost"


def test_limit_exceeded_is_terminal_and_does_not_persist_result(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Limit", "email": "limit@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    job_id = create_job(client, auth["csrf_token"]).json()["job_id"]
    class Limited:
        def analyze(self, *_args, **_kwargs): raise EvidenceSizeLimitError("internal detail")
    AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Limited).process_next()

    payload = client.get(f"/api/v1/analysis-jobs/{job_id}").json()
    assert payload["status"] == "LIMIT_EXCEEDED"
    assert payload["error_code"] == "limit_exceeded"
    assert client.get(f"/api/v1/analysis-jobs/{job_id}/result").status_code == 409
    assert list(storage.root.iterdir()) == []


def test_analysis_set_uses_completed_jobs_without_reopening_files(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Set", "email": "set@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    first = create_job(client, auth["csrf_token"]).json()["job_id"]
    second = create_job(client, auth["csrf_token"]).json()["job_id"]
    values = iter([
        replace(contract(analysis_id="a"), evidence_id="ev-a", file={"name": "a.bin"}, hashes={"sha256": "d" * 64}),
        replace(contract(analysis_id="b"), evidence_id="ev-b", file={"name": "b.bin"}, hashes={"sha256": "d" * 64}),
    ])
    class Service:
        def analyze(self, *_args, **_kwargs):
            return next(values)
    executor = AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Service)
    executor.process_next()
    executor.process_next()
    assert list(storage.root.iterdir()) == []

    response = client.post(
        "/api/v1/analysis-sets", json={"job_ids": [first, second]},
        headers={"X-CSRF-Token": auth["csrf_token"]},
    )
    assert response.status_code == 201
    payload = response.json()
    assert payload["state"] == "completed"
    assert payload["correlation_result"]["findings"][0]["category"] == "cross_file_match"
    assert "\\" not in str(payload)
    assert client.get(f"/api/v1/analysis-sets/{payload['set_id']}").json() == payload


def test_failed_job_is_analysis_set_limitation(platform) -> None:
    client, factory, tmp_path = platform
    auth = client.post("/api/v1/auth/register", json={"name": "Partial", "email": "partial-set@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    good = create_job(client, auth["csrf_token"]).json()["job_id"]
    bad = create_job(client, auth["csrf_token"]).json()["job_id"]
    calls = 0
    class Sequence:
        def analyze(self, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("internal")
            return replace(contract(), evidence_id="ev-good")
    executor = AnalysisJobExecutor(factory, storage=storage, analysis_service_factory=Sequence)
    executor.process_next()
    executor.process_next()
    response = client.post("/api/v1/analysis-sets", json={"job_ids": [good, bad]}, headers={"X-CSRF-Token": auth["csrf_token"]})
    assert response.status_code == 201
    assert response.json()["state"] == "partial"
    assert len(response.json()["limitations"]) == 1


def test_analysis_set_rejects_foreign_or_running_jobs(platform) -> None:
    client, _factory, tmp_path = platform
    owner = client.post("/api/v1/auth/register", json={"name": "Owner Set", "email": "owner-set@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    storage = UploadStorage(root=tmp_path / "jobs", max_file_size_bytes=32)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    job = create_job(client, owner["csrf_token"]).json()["job_id"]
    not_ready = client.post("/api/v1/analysis-sets", json={"job_ids": [job]}, headers={"X-CSRF-Token": owner["csrf_token"]})
    assert not_ready.status_code == 409
    client.cookies.clear()
    other = client.post("/api/v1/auth/register", json={"name": "Other Set", "email": "other-set@example.test", "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True}).json()
    foreign = client.post("/api/v1/analysis-sets", json={"job_ids": [job]}, headers={"X-CSRF-Token": other["csrf_token"]})
    assert foreign.status_code == 404

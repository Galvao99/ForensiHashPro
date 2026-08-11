from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.contracts import AnalysisContract, AnalysisState
from web.backend.app.api.routes import (
    get_analysis_job_executor,
    get_upload_storage,
)
from web.backend.app.database import Base, get_db
from web.backend.app.main import app
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, RetentionMode
from web.backend.app.services import AnalysisJobExecutor, UploadStorage


class WakeOnly:
    def wake(self) -> None:
        return None


def _contract(analysis_id: str) -> AnalysisContract:
    return AnalysisContract(
        schema_version="1.0.0",
        analysis_id=analysis_id,
        evidence_id=f"evidence-{analysis_id}",
        state=AnalysisState.COMPLETED,
        file={"name": "sample.txt", "size_bytes": 4},
        hashes={"sha256": sha256(b"data").hexdigest()},
        declared_type=".txt",
        detected_type="TEXT",
    )


def _database(tmp_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'jobs.sqlite3'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _queued_job(factory, storage: UploadStorage, analysis_id: str) -> None:
    workspace = storage.root / f"request-{analysis_id}"
    workspace.mkdir(parents=True)
    path = workspace / "evidence.txt"
    path.write_bytes(b"data")
    with factory() as db:
        db.add(
            AnalysisJob(
                id=analysis_id,
                status=AnalysisJobStatus.QUEUED.value,
                original_filename="sample.txt",
                retention_mode=RetentionMode.PRIVATE.value,
                staging_path=str(path),
                staging_sha256=sha256(b"data").hexdigest(),
                size_bytes=4,
                current_stage="QUEUED",
            )
        )
        db.commit()


def test_two_jobs_run_concurrently_without_duplicate_claim(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)
    _queued_job(factory, storage, "analysis-one")
    _queued_job(factory, storage, "analysis-two")
    entered = threading.Barrier(3)
    release = threading.Event()
    calls: list[str] = []
    lock = threading.Lock()

    class SlowService:
        def analyze(self, _path, *, analysis_id=None, **_kwargs):
            with lock:
                calls.append(analysis_id)
            entered.wait(timeout=5)
            release.wait(timeout=5)
            return _contract(analysis_id)

    executor = AnalysisJobExecutor(
        factory,
        storage=storage,
        analysis_service_factory=SlowService,
        max_concurrency=2,
        isolate_process=False,
        poll_interval=0.01,
    )
    try:
        executor.start()
        entered.wait(timeout=5)
        with factory() as db:
            assert set(db.scalars(select(AnalysisJob.status))) == {"PROCESSING"}
        release.set()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            with factory() as db:
                if set(db.scalars(select(AnalysisJob.status))) == {"SUCCESS"}:
                    break
            time.sleep(0.02)
        assert sorted(calls) == ["analysis-one", "analysis-two"]
    finally:
        release.set()
        executor.stop()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_global_timeout_terminates_isolated_process_and_cleans_staging(
    tmp_path: Path,
) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)
    _queued_job(factory, storage, "timed-analysis")
    executor = AnalysisJobExecutor(
        factory,
        storage=storage,
        timeout_seconds=0.01,
        isolate_process=True,
    )

    assert executor.process_next() is True

    with factory() as db:
        job = db.get(AnalysisJob, "timed-analysis")
        assert job.status == "FAILED"
        assert job.error_code == "analysis_timeout"
        assert job.finished_at is not None
    assert list(storage.root.iterdir()) == []
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_isolated_process_preserves_analysis_contract(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("FORENSIHASH_TEMP_DIR", str(tmp_path / "core-temp"))
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)
    _queued_job(factory, storage, "isolated-analysis")
    executor = AnalysisJobExecutor(
        factory,
        storage=storage,
        timeout_seconds=30,
        isolate_process=True,
    )

    assert executor.process_next() is True

    with factory() as db:
        job = db.get(AnalysisJob, "isolated-analysis")
        assert job.status in {"SUCCESS", "PARTIAL"}
        assert job.result_analysis_id == "isolated-analysis"
        assert job.result_json["analysis_id"] == "isolated-analysis"
        assert job.result_json["schema_version"] == "1.0.0"
    assert list(storage.root.iterdir()) == []
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_queue_capacity_rejects_before_staging(
    tmp_path: Path, monkeypatch
) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)

    def database_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    monkeypatch.setenv("FORENSIHASH_ANALYSIS_QUEUE_CAPACITY", "1")
    try:
        with TestClient(app) as client:
            auth = client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Capacity",
                    "email": "capacity@example.test",
                    "password": "correct-horse-42",
                    "accept_terms": True,
                    "accept_privacy": True,
                },
            ).json()
            headers = {"X-CSRF-Token": auth["csrf_token"]}
            assert client.get(
                "/api/v1/analysis-jobs/00000000-0000-0000-0000-000000000000/result"
            ).status_code == 404
            first = client.post(
                "/api/v1/analysis-jobs",
                files={"file": ("one.txt", b"data")},
                data={"private_session": "true"},
                headers=headers,
            )
            second = client.post(
                "/api/v1/analysis-jobs",
                files={"file": ("two.txt", b"data")},
                data={"private_session": "true"},
                headers=headers,
            )
        assert first.status_code == 202
        assert first.json()["analysis_id"] == first.json()["job_id"]
        assert first.json()["state"] == "queued"
        assert second.status_code == 429
        assert second.json()["error"]["code"] == "analysis_capacity_reached"
        assert len(list(storage.root.iterdir())) == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_health_responds_while_legacy_analysis_is_heavy(tmp_path: Path) -> None:
    started = threading.Event()
    release = threading.Event()

    class SlowService:
        def analyze(self, *_args, **_kwargs):
            started.set()
            release.wait(timeout=5)
            return _contract("legacy-analysis")

    from web.backend.app.api.routes import get_web_analysis_service

    app.dependency_overrides[get_web_analysis_service] = SlowService
    try:
        with TestClient(app) as client, ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(
                client.post,
                "/api/v1/analyses",
                files={"file": ("sample.txt", b"data")},
            )
            assert started.wait(timeout=5)
            before = time.monotonic()
            health = client.get("/health")
            assert health.status_code == 200
            assert time.monotonic() - before < 1
            release.set()
            assert pending.result(timeout=5).status_code == 200
    finally:
        release.set()
        app.dependency_overrides.clear()

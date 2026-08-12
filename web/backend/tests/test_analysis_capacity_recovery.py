from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web.backend.app.api.routes import get_analysis_job_executor, get_upload_storage
from web.backend.app.database import Base, get_db
from web.backend.app.main import app
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, RetentionMode
from web.backend.app.services import (
    ACTIVE_JOB_STATUSES,
    AnalysisJobExecutor,
    UploadStorage,
    analysis_capacity_guard,
    analysis_capacity_snapshot,
)


class WakeOnly:
    def wake(self) -> None:
        return None


def _database(tmp_path: Path):
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'capacity.sqlite3'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    Base.metadata.create_all(engine)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _job(
    job_id: str,
    status: AnalysisJobStatus,
    *,
    staging_path: Path | None = None,
    worker_token: str | None = None,
    heartbeat_at: datetime | None = None,
) -> AnalysisJob:
    return AnalysisJob(
        id=job_id,
        status=status.value,
        original_filename="sample.pdf",
        retention_mode=RetentionMode.PRIVATE.value,
        staging_path=str(staging_path) if staging_path else None,
        staging_sha256=sha256(b"%PDF-1.4").hexdigest(),
        size_bytes=8,
        current_stage="ANALYZING" if status is AnalysisJobStatus.PROCESSING else status.value,
        worker_token=worker_token,
        heartbeat_at=heartbeat_at,
    )


@pytest.mark.parametrize(
    ("status", "expected_active"),
    [
        (AnalysisJobStatus.SUCCESS, 0),
        (AnalysisJobStatus.PARTIAL, 0),
        (AnalysisJobStatus.FAILED, 0),
        (AnalysisJobStatus.QUEUED, 1),
        (AnalysisJobStatus.PROCESSING, 1),
    ],
)
def test_capacity_counts_only_operationally_active_states(
    tmp_path: Path, status: AnalysisJobStatus, expected_active: int
) -> None:
    engine, factory = _database(tmp_path)
    try:
        with factory() as db:
            db.add(_job("job-state", status))
            db.commit()
            snapshot = analysis_capacity_snapshot(db, 2)
        assert snapshot.active_jobs == expected_active
        assert snapshot.available_slots == 2 - expected_active
        assert ACTIVE_JOB_STATUSES == {"QUEUED", "PROCESSING"}
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_zero_jobs_has_non_negative_capacity(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    try:
        with factory() as db:
            snapshot = analysis_capacity_snapshot(db, 1)
        assert snapshot.active_jobs == 0
        assert snapshot.available_slots == 1
        assert analysis_capacity_snapshot(db, -1).available_slots == 0
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_restart_requeues_foreign_processing_job_immediately(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)
    staged = storage.root / "request-old" / "evidence.pdf"
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b"%PDF-1.4")
    with factory() as db:
        db.add(
            _job(
                "old-processing",
                AnalysisJobStatus.PROCESSING,
                staging_path=staged,
                worker_token="dead-executor",
                heartbeat_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    restarted = AnalysisJobExecutor(factory, storage=storage, isolate_process=False)
    try:
        restarted.recover()
        with factory() as db:
            recovered = db.get(AnalysisJob, "old-processing")
            assert recovered.status == AnalysisJobStatus.QUEUED.value
            assert recovered.worker_token is None
            assert recovered.heartbeat_at is None
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_dead_executor_without_staging_frees_capacity_and_accepts_new_pdf(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)
    executor = AnalysisJobExecutor(
        factory,
        storage=storage,
        isolate_process=False,
    )
    try:
        with factory() as db:
            db.add(
                _job(
                    "lost-processing",
                    AnalysisJobStatus.PROCESSING,
                    worker_token="dead-executor",
                    heartbeat_at=datetime.now(timezone.utc) - timedelta(hours=1),
                )
            )
            db.commit()
        executor.recover()
        with factory() as db:
            job = db.get(AnalysisJob, "lost-processing")
            snapshot = analysis_capacity_snapshot(db, 1)
        assert job.status == AnalysisJobStatus.FAILED.value
        assert job.error_code == "staging_lost"
        assert snapshot.available_slots == 1

        def database_override():
            with factory() as db:
                yield db

        app.dependency_overrides[get_db] = database_override
        app.dependency_overrides[get_upload_storage] = lambda: storage
        app.dependency_overrides[get_analysis_job_executor] = WakeOnly
        monkeypatch.setenv("FORENSIHASH_ANALYSIS_QUEUE_CAPACITY", "1")
        with TestClient(app) as client:
            auth = client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Restart PDF",
                    "email": "restart-pdf@example.test",
                    "password": "correct-horse-42",
                    "accept_terms": True,
                    "accept_privacy": True,
                },
            ).json()
            response = client.post(
                "/api/v1/analysis-jobs",
                files={"file": ("normal.pdf", b"%PDF-1.4")},
                data={"private_session": "true"},
                headers={"X-CSRF-Token": auth["csrf_token"]},
            )
        assert response.status_code == 202
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_two_concurrent_admissions_cannot_exceed_capacity(tmp_path: Path) -> None:
    engine, factory = _database(tmp_path)
    barrier = threading.Barrier(2)

    def admit(index: int) -> bool:
        barrier.wait(timeout=5)
        with factory() as db, analysis_capacity_guard(db):
            if analysis_capacity_snapshot(db, 1).available_slots == 0:
                return False
            db.add(_job(f"concurrent-{index}", AnalysisJobStatus.QUEUED))
            db.commit()
            return True

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            admitted = list(pool.map(admit, (1, 2)))
        assert sorted(admitted) == [False, True]
        with factory() as db:
            assert analysis_capacity_snapshot(db, 1).active_jobs == 1
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


def test_capacity_rejection_logs_safe_operational_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    engine, factory = _database(tmp_path)
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=32)

    def database_override():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_upload_storage] = lambda: storage
    app.dependency_overrides[get_analysis_job_executor] = WakeOnly
    monkeypatch.setenv("FORENSIHASH_ANALYSIS_QUEUE_CAPACITY", "1")
    try:
        with factory() as db:
            db.add(_job("already-queued", AnalysisJobStatus.QUEUED))
            db.commit()
        with TestClient(app) as client:
            auth = client.post(
                "/api/v1/auth/register",
                json={
                    "name": "Capacity Log",
                    "email": "capacity-log@example.test",
                    "password": "correct-horse-42",
                    "accept_terms": True,
                    "accept_privacy": True,
                },
            ).json()
            with caplog.at_level("WARNING", logger="forensihash.web"):
                response = client.post(
                    "/api/v1/analysis-jobs",
                    files={"file": ("sample.pdf", b"%PDF-1.4")},
                    data={"private_session": "true"},
                    headers={"X-CSRF-Token": auth["csrf_token"]},
                )
        assert response.status_code == 429
        record = next(item for item in caplog.records if item.msg == "analysis_capacity_reached")
        assert (record.configured_capacity, record.active_jobs) == (1, 1)
        assert (record.queued_jobs, record.running_jobs) == (1, 0)
        assert not hasattr(record, "staging_path")
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()

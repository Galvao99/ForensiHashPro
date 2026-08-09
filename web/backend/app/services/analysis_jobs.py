from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session, sessionmaker

from app.application.analysis_coordinator import AnalysisCancelledError
from app.evidence import EvidenceAcquisitionError, EvidenceIntegrityError, EvidenceSizeLimitError
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, RetentionMode, StoredAnalysis
from web.backend.app.presentation import AnalysisPresenter
from web.backend.app.services.analysis_service import UploadIntegrityError, UploadStorage, WebAnalysisService

LOGGER = logging.getLogger("forensihash.web.jobs")
PRIVATE_RESULT_TTL = timedelta(hours=1)
HEARTBEAT_INTERVAL_SECONDS = 10
ABANDONED_AFTER = timedelta(seconds=30)
TERMINAL_JOB_STATUSES = frozenset(status.value for status in (
    AnalysisJobStatus.SUCCESS, AnalysisJobStatus.PARTIAL, AnalysisJobStatus.FAILED,
    AnalysisJobStatus.LIMIT_EXCEEDED, AnalysisJobStatus.CANCELLED,
))


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisJobExecutor:
    """Fila interna V1 com estado persistente e concorrência unitária."""

    def __init__(self, session_factory: sessionmaker[Session], *, storage: UploadStorage | None = None,
                 analysis_service_factory: Callable[[], WebAnalysisService] = WebAnalysisService,
                 presenter_factory: Callable[[], AnalysisPresenter] = AnalysisPresenter,
                 poll_interval: float = 1.0) -> None:
        self._session_factory = session_factory
        self._storage = storage or UploadStorage()
        self._analysis_service_factory = analysis_service_factory
        self._presenter_factory = presenter_factory
        self._poll_interval = poll_interval
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._worker_token = str(uuid4())

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self.recover()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="analysis-job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=5)

    def wake(self) -> None:
        if not self._thread or not self._thread.is_alive():
            self.start()
        self._wake.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.process_next():
                    self._wake.wait(self._poll_interval)
                    self._wake.clear()
            except Exception as error:
                LOGGER.error("analysis_job_worker_error", extra={"error_type": type(error).__name__})
                time.sleep(self._poll_interval)

    def recover(self) -> None:
        with self._session_factory() as db:
            abandoned = self._abandoned(db)
            for job in abandoned:
                if job.staging_path and Path(job.staging_path).is_file():
                    job.status = AnalysisJobStatus.QUEUED.value
                    job.current_stage = "QUEUED"
                    job.started_at = None
                    job.worker_token = None
                    job.heartbeat_at = None
                else:
                    self._fail_staging_lost(job)
            db.commit()
            active = {
                Path(path) for path in db.scalars(
                    select(AnalysisJob.staging_path).where(
                        AnalysisJob.status.in_((AnalysisJobStatus.QUEUED.value, AnalysisJobStatus.PROCESSING.value)),
                        AnalysisJob.staging_path.is_not(None),
                    )
                ) if path
            }
        self._storage.cleanup_orphans(active)

    def process_next(self) -> bool:
        with self._session_factory() as db:
            for job in self._abandoned(db):
                if job.staging_path and Path(job.staging_path).is_file():
                    job.status = AnalysisJobStatus.QUEUED.value
                    job.current_stage = "QUEUED"
                    job.started_at = None
                    job.worker_token = None
                    job.heartbeat_at = None
                else:
                    self._fail_staging_lost(job)
            db.execute(
                update(AnalysisJob)
                .where(
                    AnalysisJob.result_expires_at.is_not(None),
                    AnalysisJob.result_expires_at <= _utcnow(),
                    AnalysisJob.result_json.is_not(None),
                )
                .values(result_json=None)
            )
            db.commit()
            candidate = db.scalar(select(AnalysisJob.id).where(AnalysisJob.status == AnalysisJobStatus.QUEUED.value).order_by(AnalysisJob.created_at, AnalysisJob.id).limit(1))
            if candidate is None:
                return False
            claimed = db.execute(update(AnalysisJob).where(AnalysisJob.id == candidate, AnalysisJob.status == AnalysisJobStatus.QUEUED.value).values(status=AnalysisJobStatus.PROCESSING.value, current_stage="ANALYZING", started_at=_utcnow(), worker_token=self._worker_token, heartbeat_at=_utcnow()))
            if claimed.rowcount != 1:
                db.rollback()
                return True
            db.commit()
        self._process(candidate)
        return True

    def _process(self, job_id: str) -> None:
        started = time.monotonic()
        with self._session_factory() as db:
            job = db.get(AnalysisJob, job_id)
            if job is None or job.status != AnalysisJobStatus.PROCESSING.value:
                return
            staged_path = Path(job.staging_path) if job.staging_path else None
            if staged_path is None or not staged_path.is_file():
                self._fail_staging_lost(job)
                db.commit()
                return
            try:
                heartbeat_stop = threading.Event()
                heartbeat = threading.Thread(target=self._heartbeat, args=(job.id, heartbeat_stop), daemon=True)
                heartbeat.start()
                contract = self._analysis_service_factory().analyze(staged_path, staging_sha256=job.staging_sha256)
                job.current_stage = "CONSOLIDATING"
                payload = self._presenter_factory().present(contract, display_name=job.original_filename)
                job.result_analysis_id = contract.analysis_id
                job.status = {"completed": AnalysisJobStatus.SUCCESS.value, "partial": AnalysisJobStatus.PARTIAL.value, "cancelled": AnalysisJobStatus.CANCELLED.value}.get(contract.state.value, AnalysisJobStatus.FAILED.value)
                if job.retention_mode == RetentionMode.RESULT_ONLY.value:
                    db.add(StoredAnalysis(id=contract.analysis_id, user_id=job.user_id, filename=job.original_filename,
                        detected_type=contract.detected_type, sha256=contract.hashes.get("sha256", ""), status=contract.state.value,
                        retention_mode=job.retention_mode, result_json=payload, finished_at=contract.execution.get("finished_at")))
                else:
                    job.result_json = payload
                    job.result_expires_at = _utcnow() + PRIVATE_RESULT_TTL
                job.current_stage = "FINISHED"
            except EvidenceSizeLimitError as error:
                self._fail(job, AnalysisJobStatus.LIMIT_EXCEEDED, "limit_exceeded", "O arquivo excede o limite de segurança configurado.", error)
            except AnalysisCancelledError as error:
                self._fail(job, AnalysisJobStatus.CANCELLED, "analysis_cancelled", "A análise foi cancelada.", error)
            except (UploadIntegrityError, EvidenceIntegrityError, EvidenceAcquisitionError, ValueError) as error:
                self._fail(job, AnalysisJobStatus.FAILED, "processing_failed", "A análise não pôde processar a evidência enviada.", error)
            except Exception as error:
                self._fail(job, AnalysisJobStatus.FAILED, "processing_failed", "A análise não pôde ser concluída.", error)
            finally:
                heartbeat_stop.set()
                heartbeat.join(timeout=2)
                job.finished_at = _utcnow()
                job.staging_path = None
                job.worker_token = None
                job.heartbeat_at = None
                try:
                    self._storage.cleanup(staged_path)
                except (OSError, RuntimeError) as cleanup_error:
                    LOGGER.error("analysis_job_cleanup_failed", extra={"job_id": job.id, "error_type": type(cleanup_error).__name__})
                db.commit()
                LOGGER.info("analysis_job_finished", extra={"job_id": job.id, "analysis_id": job.result_analysis_id, "status": job.status, "duration_ms": int((time.monotonic() - started) * 1000)})

    @staticmethod
    def _fail(job: AnalysisJob, status: AnalysisJobStatus, code: str, message: str, error: BaseException) -> None:
        job.status = status.value
        job.error_code = code
        job.safe_error_message = message
        job.current_stage = "FINISHED"
        LOGGER.warning("analysis_job_failed", extra={"job_id": job.id, "status": job.status, "error_type": type(error).__name__, "code": code})

    @staticmethod
    def _fail_staging_lost(job: AnalysisJob) -> None:
        job.status = AnalysisJobStatus.FAILED.value
        job.error_code = "staging_lost"
        job.safe_error_message = "O arquivo temporário necessário para continuar esta análise não está mais disponível."
        job.current_stage = "FINISHED"
        job.finished_at = _utcnow()
        job.staging_path = None
        job.worker_token = None
        job.heartbeat_at = None

    @staticmethod
    def _abandoned(db: Session) -> list[AnalysisJob]:
        cutoff = _utcnow() - ABANDONED_AFTER
        return list(db.scalars(select(AnalysisJob).where(
            AnalysisJob.status == AnalysisJobStatus.PROCESSING.value,
            (AnalysisJob.heartbeat_at.is_(None)) | (AnalysisJob.heartbeat_at < cutoff),
        )))

    def _heartbeat(self, job_id: str, stop: threading.Event) -> None:
        while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            with self._session_factory() as db:
                db.execute(update(AnalysisJob).where(
                    AnalysisJob.id == job_id,
                    AnalysisJob.status == AnalysisJobStatus.PROCESSING.value,
                    AnalysisJob.worker_token == self._worker_token,
                ).values(heartbeat_at=_utcnow()))
                db.commit()

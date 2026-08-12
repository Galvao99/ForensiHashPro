from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from contextlib import contextmanager
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session, sessionmaker

from app.application.analysis_coordinator import AnalysisCancelledError
from app.evidence import EvidenceAcquisitionError, EvidenceIntegrityError, EvidenceSizeLimitError
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, RetentionMode, StoredAnalysis
from web.backend.app.presentation import AnalysisPresenter
from web.backend.app.services.analysis_service import UploadIntegrityError, UploadStorage, WebAnalysisService
from web.backend.app.runtime_config import analysis_concurrency, analysis_timeout_seconds

LOGGER = logging.getLogger("forensihash.web.jobs")
PRIVATE_RESULT_TTL = timedelta(hours=1)
HEARTBEAT_INTERVAL_SECONDS = 10
ABANDONED_AFTER = timedelta(seconds=30)
TERMINAL_JOB_STATUSES = frozenset(status.value for status in (
    AnalysisJobStatus.SUCCESS, AnalysisJobStatus.PARTIAL, AnalysisJobStatus.FAILED,
    AnalysisJobStatus.LIMIT_EXCEEDED, AnalysisJobStatus.CANCELLED,
))
ACTIVE_JOB_STATUSES = frozenset((
    AnalysisJobStatus.QUEUED.value,
    AnalysisJobStatus.PROCESSING.value,
))
_CAPACITY_LOCK = threading.Lock()
_POSTGRES_CAPACITY_LOCK_ID = 4_602_673_457


@dataclass(frozen=True, slots=True)
class AnalysisCapacitySnapshot:
    configured_capacity: int
    queued_jobs: int
    running_jobs: int

    @property
    def active_jobs(self) -> int:
        return max(0, self.queued_jobs) + max(0, self.running_jobs)

    @property
    def available_slots(self) -> int:
        return max(0, self.configured_capacity - self.active_jobs)


@contextmanager
def analysis_capacity_guard(db: Session):
    """Serializa recuperação, contagem e INSERT entre requisições concorrentes."""
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": _POSTGRES_CAPACITY_LOCK_ID},
        )
        yield
        return
    with _CAPACITY_LOCK:
        yield


def analysis_capacity_snapshot(
    db: Session, configured_capacity: int
) -> AnalysisCapacitySnapshot:
    counts = dict(
        db.execute(
            select(AnalysisJob.status, func.count(AnalysisJob.id))
            .where(AnalysisJob.status.in_(ACTIVE_JOB_STATUSES))
            .group_by(AnalysisJob.status)
        ).all()
    )
    return AnalysisCapacitySnapshot(
        configured_capacity=max(0, configured_capacity),
        queued_jobs=max(0, int(counts.get(AnalysisJobStatus.QUEUED.value, 0))),
        running_jobs=max(0, int(counts.get(AnalysisJobStatus.PROCESSING.value, 0))),
    )


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisGlobalTimeoutError(TimeoutError):
    """O processo isolado excedeu o prazo global do job."""


def _isolated_analysis_target(
    connection: object,
    staged_path: str,
    staging_sha256: str,
    analysis_id: str,
) -> None:
    """Entry point picklable do processo; nunca envia detalhes da evidência."""
    try:
        contract = WebAnalysisService().analyze(
            Path(staged_path),
            staging_sha256=staging_sha256,
            analysis_id=analysis_id,
        )
        connection.send(("ok", contract))  # type: ignore[attr-defined]
    except BaseException as error:
        category = (
            "limit"
            if isinstance(error, EvidenceSizeLimitError)
            else "cancelled"
            if isinstance(error, AnalysisCancelledError)
            else "evidence"
            if isinstance(
                error,
                (UploadIntegrityError, EvidenceIntegrityError, EvidenceAcquisitionError, ValueError),
            )
            else "internal"
        )
        connection.send(("error", category, type(error).__name__))  # type: ignore[attr-defined]
    finally:
        connection.close()  # type: ignore[attr-defined]


class AnalysisJobExecutor:
    """Fila interna V1 persistente com concorrência e isolamento configuráveis."""

    def __init__(self, session_factory: sessionmaker[Session], *, storage: UploadStorage | None = None,
                 analysis_service_factory: Callable[[], WebAnalysisService] = WebAnalysisService,
                 presenter_factory: Callable[[], AnalysisPresenter] = AnalysisPresenter,
                 poll_interval: float = 1.0,
                 max_concurrency: int | None = None,
                 timeout_seconds: float | None = None,
                 isolate_process: bool | None = None) -> None:
        self._session_factory = session_factory
        self._storage = storage or UploadStorage()
        self._analysis_service_factory = analysis_service_factory
        self._presenter_factory = presenter_factory
        self._poll_interval = poll_interval
        self._max_concurrency = max_concurrency or analysis_concurrency()
        self._timeout_seconds = timeout_seconds or analysis_timeout_seconds()
        if self._max_concurrency <= 0 or self._timeout_seconds <= 0:
            raise ValueError("Concorrência e timeout devem ser maiores que zero.")
        self._isolate_process = (
            analysis_service_factory is WebAnalysisService
            if isolate_process is None
            else isolate_process
        )
        self._wake = threading.Event()
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._processes: set[multiprocessing.Process] = set()
        self._process_lock = threading.Lock()
        self._lifecycle_lock = threading.RLock()
        self._worker_token = str(uuid4())

    def start(self) -> None:
        with self._lifecycle_lock:
            if any(thread.is_alive() for thread in self._threads):
                return
            self.recover()
            self._stop.clear()
            self._threads = [
                threading.Thread(
                    target=self._run,
                    name=f"analysis-job-worker-{index + 1}",
                    daemon=True,
                )
                for index in range(self._max_concurrency)
            ]
            for thread in self._threads:
                thread.start()

    def stop(self) -> None:
        with self._lifecycle_lock:
            self._stop.set()
            self._wake.set()
            with self._process_lock:
                processes = tuple(self._processes)
            for process in processes:
                self._terminate_process(process)
            for thread in self._threads:
                thread.join(timeout=5)
            self._threads.clear()

    def wake(self) -> None:
        if not any(thread.is_alive() for thread in self._threads):
            self.start()
        self._wake.set()

    @property
    def worker_token(self) -> str:
        return self._worker_token

    @property
    def max_concurrency(self) -> int:
        return self._max_concurrency

    def executor_state(self) -> str:
        if self._stop.is_set():
            return "stopped"
        if any(thread.is_alive() for thread in self._threads):
            return "available"
        return "not_started"

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if not self.process_next():
                    self._wake.wait(self._poll_interval)
                    self._wake.clear()
            except Exception as error:
                LOGGER.error("analysis_job_worker_error", extra={"status": "failed", "stage": "worker_loop", "engine": "job_executor", "error_type": type(error).__name__})
                time.sleep(self._poll_interval)

    def recover(self) -> None:
        with self._session_factory() as db:
            self.recover_abandoned(db, recover_foreign_workers=True)
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

    def recover_abandoned(
        self, db: Session, *, recover_foreign_workers: bool = False
    ) -> int:
        recovered = 0
        for job in self._abandoned(
            db,
            current_worker_token=self._worker_token,
            recover_foreign_workers=recover_foreign_workers,
        ):
            if job.staging_path and Path(job.staging_path).is_file():
                job.status = AnalysisJobStatus.QUEUED.value
                job.current_stage = "QUEUED"
                job.started_at = None
                job.worker_token = None
                job.heartbeat_at = None
            else:
                self._fail_staging_lost(job)
            recovered += 1
        if recovered:
            LOGGER.warning(
                "analysis_jobs_recovered",
                extra={
                    "stage": "recovery",
                    "engine": "job_executor",
                    "status": "completed",
                    "recovered_jobs": recovered,
                },
            )
        return recovered

    def process_next(self) -> bool:
        with self._session_factory() as db:
            self.recover_abandoned(db)
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
                contract = self._execute_analysis(job, staged_path)
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
            except AnalysisGlobalTimeoutError as error:
                self._fail(job, AnalysisJobStatus.FAILED, "analysis_timeout", "A análise excedeu o tempo máximo configurado.", error)
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
                    LOGGER.error("analysis_job_cleanup_failed", extra={"job_id": job.id, "analysis_id": job.id, "stage": "cleanup", "engine": "upload_storage", "status": "failed", "error_type": type(cleanup_error).__name__})
                db.commit()
                LOGGER.info("analysis_job_finished", extra={"job_id": job.id, "analysis_id": job.id, "stage": "finished", "engine": "analysis_coordinator", "status": job.status, "duration_ms": int((time.monotonic() - started) * 1000)})

    def _execute_analysis(self, job: AnalysisJob, staged_path: Path):
        if not self._isolate_process:
            return self._analysis_service_factory().analyze(
                staged_path,
                staging_sha256=job.staging_sha256,
                analysis_id=job.id,
            )

        context = multiprocessing.get_context("spawn")
        receive, send = context.Pipe(duplex=False)
        process = context.Process(
            target=_isolated_analysis_target,
            args=(send, str(staged_path), job.staging_sha256, job.id),
            name=f"analysis-{job.id}",
        )
        started = False
        try:
            process.start()
            started = True
            with self._process_lock:
                self._processes.add(process)
            send.close()
            deadline = time.monotonic() + self._timeout_seconds
            message = None
            while process.is_alive() or receive.poll():
                if receive.poll(0.05):
                    message = receive.recv()
                    break
                if self._stop.is_set():
                    self._terminate_process(process)
                    raise AnalysisCancelledError("Executor encerrado durante a análise.")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._terminate_process(process)
                    raise AnalysisGlobalTimeoutError(
                        "O processo da análise excedeu o prazo global."
                    )
                process.join(timeout=min(0.15, remaining))
            process.join(timeout=1)
            if message is None and receive.poll():
                message = receive.recv()
            if message is None:
                raise RuntimeError("O processo de análise terminou sem resultado.")
            if message[0] == "ok":
                return message[1]
            category = message[1]
            if category == "limit":
                raise EvidenceSizeLimitError("Limite excedido no processo isolado.")
            if category == "cancelled":
                raise AnalysisCancelledError("Análise cancelada no processo isolado.")
            if category == "evidence":
                raise ValueError("A evidência foi rejeitada no processo isolado.")
            raise RuntimeError(f"Falha interna isolada: {message[2]}")
        finally:
            receive.close()
            send.close()
            if started and process.is_alive():
                self._terminate_process(process)
            if started:
                process.join(timeout=1)
            process.close()
            with self._process_lock:
                self._processes.discard(process)

    @staticmethod
    def _terminate_process(process: multiprocessing.Process) -> None:
        if not process.is_alive():
            return
        process.terminate()
        process.join(timeout=2)
        if process.is_alive() and hasattr(process, "kill"):
            process.kill()
            process.join(timeout=2)

    @staticmethod
    def _fail(job: AnalysisJob, status: AnalysisJobStatus, code: str, message: str, error: BaseException) -> None:
        job.status = status.value
        job.error_code = code
        job.safe_error_message = message
        job.current_stage = "FINISHED"
        LOGGER.warning("analysis_job_failed", extra={"job_id": job.id, "analysis_id": job.id, "stage": job.current_stage, "engine": "analysis_coordinator", "status": job.status, "error_type": type(error).__name__, "code": code})

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
    def _abandoned(
        db: Session,
        *,
        current_worker_token: str | None = None,
        recover_foreign_workers: bool = False,
    ) -> list[AnalysisJob]:
        cutoff = _utcnow() - ABANDONED_AFTER
        conditions = [
            AnalysisJob.heartbeat_at.is_(None),
            AnalysisJob.heartbeat_at < cutoff,
        ]
        if recover_foreign_workers and current_worker_token is not None:
            conditions.append(AnalysisJob.worker_token != current_worker_token)
        from sqlalchemy import or_

        return list(
            db.scalars(
                select(AnalysisJob).where(
                    AnalysisJob.status == AnalysisJobStatus.PROCESSING.value,
                    or_(*conditions),
                )
            )
        )

    def _heartbeat(self, job_id: str, stop: threading.Event) -> None:
        while not stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            with self._session_factory() as db:
                db.execute(update(AnalysisJob).where(
                    AnalysisJob.id == job_id,
                    AnalysisJob.status == AnalysisJobStatus.PROCESSING.value,
                    AnalysisJob.worker_token == self._worker_token,
                ).values(heartbeat_at=_utcnow()))
                db.commit()

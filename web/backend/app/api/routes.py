from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.application.analysis_coordinator import AnalysisCancelledError
from app.evidence import (
    EvidenceAcquisitionError,
    EvidenceIntegrityError,
    EvidenceSizeLimitError,
)
from web.backend.app.errors import WebApiError
from web.backend.app.api.dependencies import current_user, optional_user, require_csrf
from web.backend.app.database import SessionFactory, get_db
from web.backend.app.models import AnalysisJob, AnalysisJobStatus, AnalysisSetRecord, RetentionMode, StoredAnalysis, User
from web.backend.app.presentation import AnalysisPresenter
from web.backend.app.services import (
    CapabilitiesService,
    EmptyUploadError,
    UploadStorage,
    UploadIntegrityError,
    UploadStagingError,
    UploadTooLargeError,
    WebAnalysisService,
    AnalysisJobExecutor,
    analysis_capacity_guard,
    analysis_capacity_snapshot,
    TERMINAL_JOB_STATUSES,
    AnalysisSetService,
)
from web.backend.app.runtime_config import (
    analysis_concurrency,
    analysis_queue_capacity,
    job_worker_enabled,
)


LOGGER = logging.getLogger("forensihash.web")
router = APIRouter(prefix="/api/v1")
JOB_EXECUTOR = AnalysisJobExecutor(SessionFactory)


def get_web_analysis_service() -> WebAnalysisService:
    return WebAnalysisService()


def get_upload_storage() -> UploadStorage:
    return UploadStorage()


def get_analysis_job_executor() -> AnalysisJobExecutor:
    return JOB_EXECUTOR


def get_analysis_presenter() -> AnalysisPresenter:
    return AnalysisPresenter()


def get_capabilities_service() -> CapabilitiesService:
    return CapabilitiesService()


def get_analysis_set_service() -> AnalysisSetService:
    return AnalysisSetService()


class AnalysisSetRequest(BaseModel):
    job_ids: list[str] = Field(min_length=1, max_length=50)


def _error(status_code: int, code: str, message: str, request_id: str) -> WebApiError:
    return WebApiError(status_code, code, message, request_id)


def _job_payload(job: AnalysisJob) -> dict[str, object]:
    public_state = {
        AnalysisJobStatus.QUEUED.value: "queued",
        AnalysisJobStatus.PROCESSING.value: "running",
        AnalysisJobStatus.SUCCESS.value: "completed",
        AnalysisJobStatus.PARTIAL.value: "partial",
    }.get(job.status, "failed")
    return {
        "job_id": job.id, "analysis_id": job.result_analysis_id or job.id,
        "status": job.status,
        "state": public_state, "created_at": job.created_at,
        "started_at": job.started_at, "finished_at": job.finished_at,
        "current_stage": job.current_stage, "result_analysis_id": job.result_analysis_id,
        "error_code": job.error_code, "safe_error_message": job.safe_error_message,
    }


@router.post("/analysis-jobs", status_code=status.HTTP_202_ACCEPTED, response_model=None)
async def create_analysis_job(
    request: Request,
    file: UploadFile = File(...),
    retention_mode: str | None = Form(default=None),
    private_session: bool = Form(default=False),
    storage: UploadStorage = Depends(get_upload_storage),
    executor: AnalysisJobExecutor = Depends(get_analysis_job_executor),
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    request_id = str(uuid4())
    require_csrf(request)
    try:
        if job_worker_enabled():
            start_executor = getattr(executor, "start", None)
            if callable(start_executor):
                start_executor()
        selected = RetentionMode.PRIVATE if private_session else RetentionMode(retention_mode or user.privacy.retention_mode)
        if selected is RetentionMode.FILE_AND_RESULT:
            raise ValueError("Retenção de arquivo indisponível.")
        staged = await storage.store(file)
        with analysis_capacity_guard(db):
            recover = getattr(executor, "recover_abandoned", None)
            if callable(recover):
                recover(db, recover_foreign_workers=True)
            configured_capacity = analysis_queue_capacity()
            capacity = analysis_capacity_snapshot(db, configured_capacity)
            if capacity.available_slots == 0:
                executor_state = getattr(executor, "executor_state", lambda: "unknown")()
                LOGGER.warning(
                    "analysis_capacity_reached",
                    extra={
                        "request_id": request_id,
                        "stage": "admission",
                        "engine": "job_executor",
                        "status": "rejected",
                        "configured_capacity": configured_capacity,
                        "active_jobs": capacity.active_jobs,
                        "queued_jobs": capacity.queued_jobs,
                        "running_jobs": capacity.running_jobs,
                        "concurrency": getattr(executor, "max_concurrency", analysis_concurrency()),
                        "executor_state": executor_state,
                    },
                )
                storage.cleanup(staged.path)
                raise _error(
                    status.HTTP_429_TOO_MANY_REQUESTS,
                    "analysis_capacity_reached",
                    "A capacidade temporária de análises foi atingida; tente novamente mais tarde.",
                    request_id,
                )
            analysis_id = str(uuid4())
            job = AnalysisJob(id=analysis_id, user_id=user.id, status=AnalysisJobStatus.QUEUED.value,
                original_filename=staged.display_name, retention_mode=selected.value,
                staging_path=str(staged.path), staging_sha256=staged.sha256,
                size_bytes=staged.size_bytes, current_stage="QUEUED")
            try:
                db.add(job)
                db.commit()
                db.refresh(job)
            except Exception:
                storage.cleanup(staged.path)
                raise
        executor.wake()
        LOGGER.info("analysis_job_created", extra={"job_id": job.id, "analysis_id": job.id, "stage": "queued", "engine": "job_executor", "status": job.status, "request_id": request_id, "size_bytes": staged.size_bytes})
        return {
            "job_id": job.id,
            "analysis_id": job.id,
            "status": job.status,
            "state": "queued",
        }
    except WebApiError:
        raise
    except UploadTooLargeError as error:
        raise _error(status.HTTP_413_CONTENT_TOO_LARGE, "file_too_large", "O arquivo excede o limite de segurança configurado.", request_id) from error
    except EmptyUploadError as error:
        raise _error(status.HTTP_400_BAD_REQUEST, "empty_upload", "O arquivo enviado está vazio.", request_id) from error
    except UploadStagingError as error:
        raise _error(status.HTTP_500_INTERNAL_SERVER_ERROR, "staging_failed", "O upload não pôde ser preparado para análise.", request_id) from error
    except ValueError as error:
        raise _error(status.HTTP_422_UNPROCESSABLE_CONTENT, "analysis_rejected", "A análise não pôde processar a entrada fornecida.", request_id) from error


@router.get("/analysis-jobs/{job_id}", response_model=None)
def analysis_job_status(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id))
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found", "Job de análise não encontrado.", str(uuid4()))
    return _job_payload(job)


@router.get("/analysis-jobs/{job_id}/result", response_model=None)
def analysis_job_result(job_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)) -> dict[str, object]:
    job = db.scalar(select(AnalysisJob).where(AnalysisJob.id == job_id, AnalysisJob.user_id == user.id))
    if job is None:
        raise _error(status.HTTP_404_NOT_FOUND, "job_not_found", "Job de análise não encontrado.", str(uuid4()))
    if job.status not in TERMINAL_JOB_STATUSES:
        raise _error(status.HTTP_409_CONFLICT, "result_not_ready", "O resultado ainda não está disponível.", str(uuid4()))
    if job.status not in {AnalysisJobStatus.SUCCESS.value, AnalysisJobStatus.PARTIAL.value}:
        raise _error(status.HTTP_409_CONFLICT, job.error_code or "result_unavailable", job.safe_error_message or "O resultado não está disponível.", str(uuid4()))
    if job.retention_mode == RetentionMode.RESULT_ONLY.value and job.result_analysis_id:
        stored = db.get(StoredAnalysis, job.result_analysis_id)
        if stored is not None and stored.user_id == user.id:
            return stored.result_json
    expires = job.result_expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if job.result_json is None or (expires is not None and expires <= datetime.now(timezone.utc)):
        job.result_json = None
        db.commit()
        raise _error(status.HTTP_410_GONE, "result_unavailable", "O resultado privado temporário não está mais disponível.", str(uuid4()))
    return job.result_json


@router.post("/analysis-sets", status_code=status.HTTP_201_CREATED, response_model=None)
def create_analysis_set(
    payload: AnalysisSetRequest,
    request: Request,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
    service: AnalysisSetService = Depends(get_analysis_set_service),
) -> dict[str, object]:
    require_csrf(request)
    return service.create(db, user, payload.job_ids).result_json


@router.get("/analysis-sets/{set_id}", response_model=None)
def get_analysis_set(
    set_id: str,
    user: User = Depends(current_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    record = db.scalar(select(AnalysisSetRecord).where(
        AnalysisSetRecord.id == set_id, AnalysisSetRecord.user_id == user.id
    ))
    if record is None:
        raise _error(status.HTTP_404_NOT_FOUND, "analysis_set_not_found", "Analysis Set não encontrado.", str(uuid4()))
    expires = record.expires_at
    if expires is not None and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires is not None and expires <= datetime.now(timezone.utc):
        raise _error(status.HTTP_410_GONE, "analysis_set_expired", "O resultado do Analysis Set expirou.", str(uuid4()))
    return record.result_json


@router.get("/capabilities", response_model=None)
def capabilities(
    service: CapabilitiesService = Depends(get_capabilities_service),
) -> dict[str, object]:
    return service.get()


@router.post("/analyses", response_model=None)
async def create_analysis(
    request: Request,
    file: UploadFile = File(...),
    retention_mode: str | None = Form(default=None),
    private_session: bool = Form(default=False),
    service: WebAnalysisService = Depends(get_web_analysis_service),
    storage: UploadStorage = Depends(get_upload_storage),
    presenter: AnalysisPresenter = Depends(get_analysis_presenter),
    user: User | None = Depends(optional_user),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    request_id = str(uuid4())
    started = time.monotonic()
    size_bytes = 0
    try:
        if user is not None:
            require_csrf(request)
        selected_retention = RetentionMode.PRIVATE
        if user is not None and not private_session:
            try:
                selected_retention = RetentionMode(retention_mode or user.privacy.retention_mode)
            except ValueError as error:
                raise ValueError("Modo de retenção inválido.") from error
        if selected_retention is RetentionMode.FILE_AND_RESULT:
            raise ValueError("Retenção permanente do arquivo ainda não está disponível.")
        async with storage.stage(file) as staged:
            size_bytes = staged.size_bytes
            contract = await asyncio.to_thread(
                service.analyze, staged.path, staging_sha256=staged.sha256
            )
            payload = presenter.present(contract, display_name=staged.display_name)
            if user is not None and selected_retention is RetentionMode.RESULT_ONLY:
                db.add(
                    StoredAnalysis(
                        id=contract.analysis_id,
                        user_id=user.id,
                        filename=staged.display_name,
                        detected_type=contract.detected_type,
                        sha256=contract.hashes.get("sha256", ""),
                        status=contract.state.value,
                        retention_mode=selected_retention.value,
                        result_json=payload,
                        finished_at=contract.execution.get("finished_at"),
                    )
                )
                db.commit()
            LOGGER.info(
                "web_analysis_completed",
                extra={
                    "request_id": request_id,
                    "size_bytes": size_bytes,
                    "status": "completed",
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "analysis_id": contract.analysis_id,
                },
            )
            return payload
    except (UploadTooLargeError, EvidenceSizeLimitError) as error:
        LOGGER.warning(
            "web_analysis_rejected",
            extra={"request_id": request_id, "size_bytes": size_bytes, "code": "file_too_large"},
        )
        raise _error(
            status.HTTP_413_CONTENT_TOO_LARGE,
            "file_too_large",
            "O arquivo excede o limite de segurança configurado.",
            request_id,
        ) from error


    except EmptyUploadError as error:
        raise _error(
            status.HTTP_400_BAD_REQUEST,
            "empty_upload",
            "O arquivo enviado está vazio.",
            request_id,
        ) from error
    except UploadStagingError as error:
        LOGGER.error(
            "web_upload_staging_failed",
            extra={
                "request_id": request_id,
                "component": "upload_storage",
                "error_type": error.cause_type,
                "operation": error.operation,
            },
        )
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "staging_failed",
            "O upload não pôde ser preparado para análise.",
            request_id,
        ) from error
    except UploadIntegrityError as error:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "upload_integrity_mismatch",
            "A integridade do upload não pôde ser confirmada.",
            request_id,
        ) from error
    except EvidenceIntegrityError as error:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "evidence_compromised",
            "A integridade da evidência não pôde ser confirmada.",
            request_id,
        ) from error
    except EvidenceAcquisitionError as error:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "evidence_acquisition_failed",
            "A evidência não pôde ser adquirida para análise.",
            request_id,
        ) from error
    except AnalysisCancelledError as error:
        raise _error(
            status.HTTP_409_CONFLICT,
            "analysis_cancelled",
            "A análise foi cancelada.",
            request_id,
        ) from error
    except ValueError as error:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "analysis_rejected",
            "A análise não pôde processar a entrada fornecida.",
            request_id,
        ) from error
    except Exception as error:
        LOGGER.error(
            "web_analysis_failed",
            extra={
                "request_id": request_id,
                "size_bytes": size_bytes,
                "status": "failed",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "code": "internal_error",
                "error_type": type(error).__name__,
            },
        )
        raise _error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "A análise não pôde ser concluída.",
            request_id,
        ) from error


@router.get("/analyses/history", response_model=None)
def analysis_history(
    user: User = Depends(current_user), db: Session = Depends(get_db)
) -> list[dict[str, object]]:
    analyses = db.scalars(
        select(StoredAnalysis)
        .where(StoredAnalysis.user_id == user.id)
        .order_by(StoredAnalysis.created_at.desc())
    )
    return [
        {
            "id": item.id,
            "filename": item.filename,
            "detected_type": item.detected_type,
            "sha256": item.sha256,
            "status": item.status,
            "retention_mode": item.retention_mode,
            "created_at": item.created_at,
            "finished_at": item.finished_at,
            "result": item.result_json,
        }
        for item in analyses
    ]

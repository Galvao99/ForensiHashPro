from __future__ import annotations

import logging
import time
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
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
from web.backend.app.database import get_db
from web.backend.app.models import RetentionMode, StoredAnalysis, User
from web.backend.app.presentation import AnalysisPresenter
from web.backend.app.services import (
    CapabilitiesService,
    EmptyUploadError,
    UploadStorage,
    UploadIntegrityError,
    UploadStagingError,
    UploadTooLargeError,
    WebAnalysisService,
)


LOGGER = logging.getLogger("forensihash.web")
router = APIRouter(prefix="/api/v1")


def get_web_analysis_service() -> WebAnalysisService:
    return WebAnalysisService()


def get_upload_storage() -> UploadStorage:
    return UploadStorage()


def get_analysis_presenter() -> AnalysisPresenter:
    return AnalysisPresenter()


def get_capabilities_service() -> CapabilitiesService:
    return CapabilitiesService()


def _error(status_code: int, code: str, message: str, request_id: str) -> WebApiError:
    return WebApiError(status_code, code, message, request_id)


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
            contract = service.analyze(staged.path, staging_sha256=staged.sha256)
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
                "technical_path": str(error.path),
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

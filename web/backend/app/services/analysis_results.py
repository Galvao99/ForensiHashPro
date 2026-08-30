from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from web.backend.app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    RetentionMode,
    StoredAnalysis,
)


_CONTRACT_JOB_STATUSES = frozenset(
    {
        AnalysisJobStatus.SUCCESS.value,
        AnalysisJobStatus.PARTIAL.value,
    }
)


def resolve_analysis_job_contract_payload(
    db: Session,
    job: AnalysisJob,
    *,
    owner_id: str,
) -> dict[str, object] | None:
    """Resolve o contrato disponível de um job sem ultrapassar seu owner."""
    return resolve_analysis_job_contract_payloads(
        db,
        [job],
        owner_id=owner_id,
    ).get(job.id)


def resolve_analysis_job_contract_payloads(
    db: Session,
    jobs: Sequence[AnalysisJob],
    *,
    owner_id: str,
) -> dict[str, dict[str, object]]:
    """Resolve contratos diretos ou retidos com uma única consulta persistida."""
    now = datetime.now(timezone.utc)
    resolved: dict[str, dict[str, object]] = {}
    retained_jobs: dict[str, list[AnalysisJob]] = defaultdict(list)

    for job in jobs:
        if job.user_id != owner_id or job.status not in _CONTRACT_JOB_STATUSES:
            continue
        if job.result_json is not None and not _is_expired(job.result_expires_at, now):
            resolved[job.id] = job.result_json
            continue
        if (
            job.retention_mode == RetentionMode.RESULT_ONLY.value
            and job.result_analysis_id
        ):
            retained_jobs[job.result_analysis_id].append(job)

    if not retained_jobs:
        return resolved

    stored_results = db.scalars(
        select(StoredAnalysis).where(
            StoredAnalysis.id.in_(retained_jobs),
            StoredAnalysis.user_id == owner_id,
            StoredAnalysis.retention_mode == RetentionMode.RESULT_ONLY.value,
        )
    )
    for stored in stored_results:
        if _is_expired(stored.expires_at, now):
            continue
        for job in retained_jobs[stored.id]:
            resolved[job.id] = stored.result_json

    return resolved


def _is_expired(expires_at: datetime | None, now: datetime) -> bool:
    if expires_at is None:
        return False
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return expires_at <= now

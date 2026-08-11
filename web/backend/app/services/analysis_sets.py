from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import AnalysisContractJson
from app.investigation.analysis_set import AnalysisSetArtifact, AnalysisSetCorrelator
from web.backend.app.errors import WebApiError
from web.backend.app.models import (
    AnalysisJob,
    AnalysisJobStatus,
    AnalysisSetRecord,
    User,
)


SET_RESULT_TTL = timedelta(hours=1)
_SUCCESS = {AnalysisJobStatus.SUCCESS.value, AnalysisJobStatus.PARTIAL.value}
_TERMINAL = _SUCCESS | {
    AnalysisJobStatus.FAILED.value,
    AnalysisJobStatus.LIMIT_EXCEEDED.value,
    AnalysisJobStatus.CANCELLED.value,
}


class AnalysisSetService:
    def __init__(self, correlator: AnalysisSetCorrelator | None = None) -> None:
        self.correlator = correlator or AnalysisSetCorrelator()

    def create(self, db: Session, user: User, job_ids: list[str]) -> AnalysisSetRecord:
        request_id = str(uuid4())
        unique_ids = list(dict.fromkeys(job_ids))
        if not unique_ids or len(unique_ids) > 50:
            raise WebApiError(422, "invalid_analysis_set", "O conjunto deve conter entre 1 e 50 jobs.", request_id)
        jobs = list(db.scalars(select(AnalysisJob).where(
            AnalysisJob.id.in_(unique_ids), AnalysisJob.user_id == user.id
        )))
        by_id = {job.id: job for job in jobs}
        if len(by_id) != len(unique_ids):
            raise WebApiError(404, "analysis_set_job_not_found", "Um ou mais jobs não foram encontrados.", request_id)
        if any(job.status not in _TERMINAL for job in jobs):
            raise WebApiError(409, "analysis_set_not_ready", "Todos os jobs devem estar em estado terminal.", request_id)
        artifacts: list[AnalysisSetArtifact] = []
        for job_id in unique_ids:
            job = by_id[job_id]
            contract = None
            limitation = None
            if job.status in _SUCCESS and job.result_json is not None:
                contract = AnalysisContractJson.loads(json.dumps(job.result_json, ensure_ascii=False))
            else:
                limitation = f"O artefato {job.original_filename} não produziu contrato utilizável ({job.status})."
            artifacts.append(AnalysisSetArtifact(
                job_id=job.id,
                analysis_id=job.result_analysis_id,
                evidence_ref=contract.evidence_id if contract else None,
                filename=str((contract.file.get("name") if contract else None) or job.original_filename),
                state=job.status.lower(),
                contract=contract,
                limitation=limitation,
            ))
        set_id = str(uuid4())
        result = self.correlator.correlate(set_id, artifacts)
        payload = self.serialize(result)
        record = AnalysisSetRecord(
            id=set_id, user_id=user.id, state=result.state, job_ids=unique_ids,
            result_json=payload, finished_at=result.finished_at,
            expires_at=datetime.now(timezone.utc) + SET_RESULT_TTL,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def serialize(result) -> dict[str, object]:
        return {
            "set_id": result.set_id,
            "state": result.state,
            "created_at": result.created_at.isoformat(),
            "finished_at": result.finished_at.isoformat(),
            "artifacts": [
                {
                    "job_id": item.job_id, "analysis_id": item.analysis_id,
                    "evidence_ref": item.evidence_ref, "filename": item.filename,
                    "state": item.state, "limitation": item.limitation,
                }
                for item in result.artifacts
            ],
            "correlation_result": {
                "summary": result.correlation_result.summary,
                "findings": [AnalysisSetService._finding(item) for item in result.correlation_result.findings],
            },
            "timeline_result": result.timeline_result,
            "limitations": list(result.limitations),
        }

    @staticmethod
    def _finding(finding) -> dict[str, object]:
        return {
            "finding_id": finding.finding_id,
            "category": finding.category,
            "severity": finding.severity,
            "summary": finding.title,
            "description": finding.description,
            "rule_id": finding.rule_id,
            "source_engine": finding.source_engine,
            "confidence": finding.confidence,
            "source_file": finding.source_file,
            "target_file": finding.target_file,
            "evidence": [asdict(item) for item in finding.evidence],
            "entities": [asdict(item) for item in finding.entities],
            "limitations": list(finding.limitations),
            "metadata": finding.metadata,
        }

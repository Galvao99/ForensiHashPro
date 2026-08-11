from __future__ import annotations

import logging

from app.processing.models import StepResult


def log_step(
    logger: logging.Logger,
    step: StepResult[object],
    *,
    analysis_id: str,
    evidence_id: str,
) -> None:
    """Registra somente identificadores e estado; nunca conteúdo ou segredo."""
    logger.info(
        "processing_step",
        extra={
            "analysis_id": analysis_id,
            "evidence_id": evidence_id,
            "component": step.component,
            "engine": step.component,
            "stage": step.code,
            "step_code": step.code,
            "status": step.status.value,
            "duration_ms": step.duration_ms,
        },
    )

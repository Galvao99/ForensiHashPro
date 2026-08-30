from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
from typing import Any

from app.contracts.serialization import json_safe
from app.correlation.v2.identity import stable_digest
from app.enum.severity import Severity
from app.processing import ProcessingStatus


CASE_RESULT_SCHEMA_VERSION = "1.0.0"


class EpistemicState(str, Enum):
    """Estado da conclusão técnica, independente de severidade e execução."""

    MATCH = "match"
    MISMATCH = "mismatch"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


_LIMITATION_STATUSES = frozenset(
    {
        ProcessingStatus.PARTIAL,
        ProcessingStatus.SKIPPED,
        ProcessingStatus.UNAVAILABLE,
        ProcessingStatus.FAILED,
        ProcessingStatus.CANCELLED,
        ProcessingStatus.LIMIT_EXCEEDED,
    }
)


@dataclass(frozen=True, slots=True)
class CaseFinding:
    """Conclusão semântica de uma regra de Caso sobre suportes factuais."""

    rule_id: str
    rule_version: str
    epistemic_state: EpistemicState
    severity: Severity
    title: str
    statement: str
    supporting_occurrence_ids: tuple[str, ...] = ()
    relation_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    finding_id: str = ""

    def __post_init__(self) -> None:
        rule_id = self.rule_id.strip()
        rule_version = self.rule_version.strip()
        if not rule_id:
            raise ValueError("Case finding rule_id must not be empty.")
        if not rule_version:
            raise ValueError("Case finding rule_version must not be empty.")
        if not self.title.strip() or not self.statement.strip():
            raise ValueError("Case finding title and statement must not be empty.")

        supports = _canonical_ids(self.supporting_occurrence_ids)
        relation_id = self.relation_id.strip() if self.relation_id else None
        if self.epistemic_state in {
            EpistemicState.MATCH,
            EpistemicState.MISMATCH,
        } and not supports:
            raise ValueError("MATCH and MISMATCH findings require factual supports.")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "rule_version", rule_version)
        object.__setattr__(self, "supporting_occurrence_ids", supports)
        object.__setattr__(self, "relation_id", relation_id)

        expected_id = case_finding_id(
            rule_id=rule_id,
            rule_version=rule_version,
            epistemic_state=self.epistemic_state,
            relation_id=relation_id,
            supporting_occurrence_ids=supports,
        )
        if self.finding_id and self.finding_id != expected_id:
            raise ValueError("Case finding ID does not match its semantic identity.")
        object.__setattr__(self, "finding_id", expected_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "epistemic_state": self.epistemic_state.value,
            "severity": self.severity.value,
            "relation_id": self.relation_id,
            "supporting_occurrence_ids": list(self.supporting_occurrence_ids),
            "title": self.title,
            "statement": self.statement,
            "metadata": json_safe(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class RuleExecutionLimitation:
    """Condição operacional de uma regra; não é evidência nem mismatch."""

    rule_id: str
    rule_version: str
    code: str
    status: ProcessingStatus
    message: str
    metadata: dict[str, Any] = field(default_factory=dict)
    limitation_id: str = ""

    def __post_init__(self) -> None:
        rule_id = self.rule_id.strip()
        rule_version = self.rule_version.strip()
        code = self.code.strip()
        if not rule_id or not rule_version or not code or not self.message.strip():
            raise ValueError("Rule limitation identity and message must not be empty.")
        if self.status not in _LIMITATION_STATUSES:
            raise ValueError(f"{self.status.value!r} is not an operational limitation status.")

        object.__setattr__(self, "rule_id", rule_id)
        object.__setattr__(self, "rule_version", rule_version)
        object.__setattr__(self, "code", code)
        expected_id = stable_digest(
            "case-rule-limitation-v1",
            [rule_id, rule_version, code, self.status.value, json_safe(self.metadata)],
        )
        if self.limitation_id and self.limitation_id != expected_id:
            raise ValueError("Rule limitation ID does not match its identity.")
        object.__setattr__(self, "limitation_id", expected_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "limitation_id": self.limitation_id,
            "rule_id": self.rule_id,
            "rule_version": self.rule_version,
            "code": self.code,
            "status": self.status.value,
            "message": self.message,
            "metadata": json_safe(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class CaseResult:
    """Envelope serializável; findings e limitações operacionais não se misturam."""

    case_id: str
    findings: tuple[CaseFinding, ...] = ()
    limitations: tuple[RuleExecutionLimitation, ...] = ()
    schema_version: str = CASE_RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        case_id = self.case_id.strip()
        if not case_id:
            raise ValueError("Case result case_id must not be empty.")
        if self.schema_version != CASE_RESULT_SCHEMA_VERSION:
            raise ValueError(f"Unsupported Case Result schema: {self.schema_version!r}.")
        findings = tuple(
            sorted({item.finding_id: item for item in self.findings}.values(), key=lambda item: item.finding_id)
        )
        limitations = tuple(
            sorted(
                {item.limitation_id: item for item in self.limitations}.values(),
                key=lambda item: item.limitation_id,
            )
        )
        object.__setattr__(self, "case_id", case_id)
        object.__setattr__(self, "findings", findings)
        object.__setattr__(self, "limitations", limitations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "findings": [item.to_dict() for item in self.findings],
            "limitations": [item.to_dict() for item in self.limitations],
        }


def case_finding_id(
    *,
    rule_id: str,
    rule_version: str,
    epistemic_state: EpistemicState,
    relation_id: str | None,
    supporting_occurrence_ids: tuple[str, ...],
) -> str:
    """Identidade canônica; adicionar suporte factual altera a identidade."""
    return stable_digest(
        "case-finding-v1",
        [
            rule_id.strip(),
            rule_version.strip(),
            epistemic_state.value,
            relation_id.strip() if relation_id else None,
            _canonical_ids(supporting_occurrence_ids),
        ],
    )


class CaseResultJson:
    @staticmethod
    def dumps(result: CaseResult, *, indent: int | None = 2) -> str:
        return json.dumps(
            result.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=indent,
            allow_nan=False,
        )

    @staticmethod
    def loads(payload: str) -> CaseResult:
        data = json.loads(payload)
        if data.get("schema_version") != CASE_RESULT_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported Case Result schema: {data.get('schema_version')!r}."
            )
        findings = tuple(
            CaseFinding(
                finding_id=item["finding_id"],
                rule_id=item["rule_id"],
                rule_version=item["rule_version"],
                epistemic_state=EpistemicState(item["epistemic_state"]),
                severity=Severity(item["severity"]),
                relation_id=item.get("relation_id"),
                supporting_occurrence_ids=tuple(item.get("supporting_occurrence_ids", ())),
                title=item["title"],
                statement=item["statement"],
                metadata=dict(item.get("metadata") or {}),
            )
            for item in data.get("findings", ())
        )
        limitations = tuple(
            RuleExecutionLimitation(
                limitation_id=item["limitation_id"],
                rule_id=item["rule_id"],
                rule_version=item["rule_version"],
                code=item["code"],
                status=ProcessingStatus(item["status"]),
                message=item["message"],
                metadata=dict(item.get("metadata") or {}),
            )
            for item in data.get("limitations", ())
        )
        return CaseResult(
            case_id=data["case_id"],
            findings=findings,
            limitations=limitations,
            schema_version=data["schema_version"],
        )


def _canonical_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    normalized = {str(value).strip() for value in values if str(value).strip()}
    return tuple(sorted(normalized))

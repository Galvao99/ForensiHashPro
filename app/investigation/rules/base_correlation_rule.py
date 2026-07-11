from abc import ABC, abstractmethod

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.models.badge import Badge


class BaseCorrelationRule(ABC):
    """
    Classe base para todas as regras de investigação.

    Centraliza métodos auxiliares para criação de Findings,
    evitando repetição de código entre as regras.
    """

    rule_id: str = ""
    name: str = ""

    @abstractmethod
    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        ...

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def add_info(
        self,
        findings: list[CorrelationFinding],
        *,
        title: str,
        description: str,
        icon: str = "",
        badges: list[Badge] | None = None,
        source_file: str | None = None,
        target_file: str | None = None,
        metadata: dict | None = None,
    ) -> None:

        findings.append(
            CorrelationFinding(
                title=title,
                description=description,
                severity="info",
                rule_id=self.rule_id,
                icon=icon,
                badges=badges or [],
                source_file=source_file,
                target_file=target_file,
                metadata=metadata or {},
            )
        )

    def add_ok(
        self,
        findings: list[CorrelationFinding],
        *,
        title: str,
        description: str,
        icon: str = "",
        badges: list[Badge] | None = None,
        source_file: str | None = None,
        target_file: str | None = None,
        metadata: dict | None = None,
    ) -> None:

        findings.append(
            CorrelationFinding(
                title=title,
                description=description,
                severity="ok",
                rule_id=self.rule_id,
                icon=icon,
                badges=badges or [],
                source_file=source_file,
                target_file=target_file,
                metadata=metadata or {},
            )
        )

    def add_warning(
        self,
        findings: list[CorrelationFinding],
        *,
        title: str,
        description: str,
        icon: str = "",
        badges: list[Badge] | None = None,
        source_file: str | None = None,
        target_file: str | None = None,
        metadata: dict | None = None,
    ) -> None:

        findings.append(
            CorrelationFinding(
                title=title,
                description=description,
                severity="warning",
                rule_id=self.rule_id,
                icon=icon,
                badges=badges or [],
                source_file=source_file,
                target_file=target_file,
                metadata=metadata or {},
            )
        )

    def add_critical(
        self,
        findings: list[CorrelationFinding],
        *,
        title: str,
        description: str,
        icon: str = "",
        badges: list[Badge] | None = None,
        source_file: str | None = None,
        target_file: str | None = None,
        metadata: dict | None = None,
    ) -> None:

        findings.append(
            CorrelationFinding(
                title=title,
                description=description,
                severity="critical",
                rule_id=self.rule_id,
                icon=icon,
                badges=badges or [],
                source_file=source_file,
                target_file=target_file,
                metadata=metadata or {},
            )
        )

    def has_metadata(
        self,
        metadata: dict,
        key: str,
    ) -> bool:

        value = metadata.get(key)

        return value not in {
            None,
            "",
        }
    
    def normalize(
        self,
        value: str | None,
    ) -> str:

        if value is None:
            return ""

        return str(value).strip()
    
    def get_metadata(
        self,
        metadata: dict,
        key: str,
        default=None,
    ):

        return metadata.get(key, default)
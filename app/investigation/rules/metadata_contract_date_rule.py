from datetime import datetime
from typing import Any

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    info_badge,
    neutral_badge,
    warning_badge,
)


class MetadataContractDateRule(BaseCorrelationRule):
    """
    Compara a data de criação registrada nos metadados
    com a data de pactuação extraída do documento.
    """

    rule_id = "metadata_contract_date"
    name = "Data de criação x data de pactuação"

    CREATE_DATE_KEYS = (
        "CreateDate",
        "PDF:CreateDate",
        "XMP:CreateDate",
        "FileCreateDate",
        "CreationDate",
    )

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for file_name, contract_date in context.contract_dates.items():
            metadata_dates = context.metadata_dates.get(
                file_name,
                {},
            )

            create_date = self._find_create_date(metadata_dates)

            if create_date is None:
                continue

            difference_days = (
                create_date.date() - contract_date.date()
            ).days

            if difference_days > 0:
                self._add_creation_after_contract_finding(
                    findings=findings,
                    file_name=file_name,
                    contract_date=contract_date,
                    create_date=create_date,
                    difference_days=difference_days,
                )

                continue

            self._add_compatible_dates_finding(
                findings=findings,
                file_name=file_name,
                contract_date=contract_date,
                create_date=create_date,
                difference_days=difference_days,
            )

        return findings

    def _add_creation_after_contract_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        contract_date: datetime,
        create_date: datetime,
        difference_days: int,
    ) -> None:
        self.add_info(
            findings,
            title="Data CreateDate posterior à data textual selecionada",
            description=(
                f"O valor declarado em CreateDate é {difference_days} dia(s) "
                "posterior à data textual selecionada como candidata contratual. "
                "CreateDate descreve o container PDF e não comprova a data de "
                "contratação nem o instante de criação do conteúdo."
            ),
            icon="calendar-warning",
            source_file=file_name,
            badges=[
                warning_badge(
                    f"+{difference_days} dia(s)",
                    tooltip=(
                        "Diferença entre a data de pactuação "
                        "e a criação do arquivo."
                    ),
                ),
                info_badge(
                    "CreateDate",
                    tooltip=(
                        "Data de criação registrada "
                        "nos metadados do arquivo."
                    ),
                ),
                neutral_badge(
                    f"Pactuação: {contract_date:%d/%m/%Y}",
                ),
                neutral_badge(
                    f"Criação: {create_date:%d/%m/%Y}",
                ),
            ],
            metadata={
                "arquivo": file_name,
                "data_pactuacao": contract_date.isoformat(),
                "data_criacao_metadados": create_date.isoformat(),
                "diferenca_dias": difference_days,
            },
        )

    def _add_compatible_dates_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        contract_date: datetime,
        create_date: datetime,
        difference_days: int,
    ) -> None:
        self.add_info(
            findings,
            title="Comparação cronológica de datas declaradas",
            description=(
                "O valor declarado em CreateDate não é posterior à data textual "
                "selecionada. Essa relação não atesta autenticidade, contratação "
                "ou origem do conteúdo."
            ),
            icon="calendar-check",
            source_file=file_name,
            badges=[
                info_badge("CreateDate"),
                neutral_badge(
                    f"Pactuação: {contract_date:%d/%m/%Y}",
                ),
                neutral_badge(
                    f"Criação: {create_date:%d/%m/%Y}",
                ),
            ],
            metadata={
                "arquivo": file_name,
                "data_pactuacao": contract_date.isoformat(),
                "data_criacao_metadados": create_date.isoformat(),
                "diferenca_dias": difference_days,
            },
        )

    def _find_create_date(
        self,
        metadata_dates: dict[str, Any],
    ) -> datetime | None:
        for key in self.CREATE_DATE_KEYS:
            value = metadata_dates.get(key)

            if isinstance(value, datetime):
                return value

        return None

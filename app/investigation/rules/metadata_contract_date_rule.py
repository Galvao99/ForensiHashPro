from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule


class MetadataContractDateRule(BaseCorrelationRule):
    rule_id = "metadata_contract_date"
    name = "Data de criação x data de pactuação"

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for file_name, contract_date in context.contract_dates.items():
            metadata_dates = context.metadata_dates.get(file_name, {})
            create_date = self._find_create_date(metadata_dates)

            if not create_date:
                continue

            if create_date.date() > contract_date.date():
                findings.append(
                    CorrelationFinding(
                        title="Data de criação posterior à pactuação",
                        message=(
                            "A data de criação identificada nos metadados do arquivo "
                            "é posterior à data de pactuação extraída do conteúdo documental. "
                            "Esse achado recomenda análise conjunta com a origem do arquivo, "
                            "logs, trilha de contratação e cadeia de custódia."
                        ),
                        severity="warning",
                        rule_id=self.rule_id,
                        related_files=[file_name],
                        evidence={
                            "arquivo": file_name,
                            "data_pactuacao": contract_date.isoformat(),
                            "data_criacao_metadados": create_date.isoformat(),
                        },
                    )
                )

        return findings

    def _find_create_date(self, metadata_dates: dict) -> object | None:
        for key in [
            "CreateDate",
            "PDF:CreateDate",
            "XMP:CreateDate",
            "FileCreateDate",
            "CreationDate",
        ]:
            if key in metadata_dates:
                return metadata_dates[key]

        return None
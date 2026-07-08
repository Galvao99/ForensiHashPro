from datetime import datetime
from typing import Any, Sequence

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models import AnalysisResult


class MetadataContractDateRule(BaseCorrelationRule):
    rule_id = "metadata_contract_date"
    name = "Data de criação x data de pactuação"

    def evaluate(
        self,
        results: Sequence[AnalysisResult],
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for result in results:
            contract_date = self._get_contract_date(result)
            create_date = self._get_create_date(result)

            if not contract_date or not create_date:
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
                        related_files=[result.file_info.name],
                        evidence={
                            "arquivo": result.file_info.name,
                            "data_pactuacao": contract_date.isoformat(),
                            "data_criacao_metadados": create_date.isoformat(),
                        },
                    )
                )

        return findings

    def _get_contract_date(self, result: AnalysisResult) -> datetime | None:
        value = getattr(result, "contract_date", None)

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            return self._parse_date(value)

        return None

    def _get_create_date(self, result: AnalysisResult) -> datetime | None:
        metadata = getattr(result, "metadata", None)

        if metadata is None:
            return None

        data: dict[str, Any] = getattr(metadata, "metadata", {}) or {}

        possible_keys = [
            "CreateDate",
            "PDF:CreateDate",
            "XMP:CreateDate",
            "FileCreateDate",
            "CreationDate",
        ]

        for key in possible_keys:
            value = data.get(key)

            parsed = self._parse_date(value)

            if parsed:
                return parsed

        return None

    def _parse_date(self, value: Any) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        text = str(value).strip()

        known_formats = [
            "%Y:%m:%d %H:%M:%S%z",
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y%m%d%H%M%SZ",
            "%d/%m/%Y",
            "%d/%m/%Y %H:%M:%S",
        ]

        for fmt in known_formats:
            try:
                return datetime.strptime(text, fmt)
            except ValueError:
                continue

        return None
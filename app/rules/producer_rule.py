from app.enum.severity import Severity
from app.knowledge.findings.producers import PRODUCER_FINDINGS
from app.knowledge.producer_database import ProducerDatabase
from app.models import Finding, MetadataResult
from app.rules.base_rule import MetadataRule


class ProducerRule(MetadataRule):
    """Interpreta Producer/Creator/Software encontrados nos metadados."""

    def apply(self, metadata: MetadataResult) -> list[Finding]:
        raw = metadata.raw if metadata else {}

        producer = self._find_first(
            raw,
            [
                "Producer",
                "PDF:Producer",
                "XMP:Producer",
                "Creator",
                "PDF:Creator",
                "XMP:Creator",
                "Software",
                "Application",
                "GeneratingApplication",
            ],
        )

        if not producer:
            return [self._missing_producer_finding()]

        knowledge_finding = self._find_in_new_knowledge_base(producer)

        if knowledge_finding:
            return [knowledge_finding]

        legacy_finding = self._find_in_legacy_database(producer)

        if legacy_finding:
            return [legacy_finding]

        return [self._unknown_producer_finding(producer)]

    def _find_in_new_knowledge_base(self, producer: str) -> Finding | None:
        normalized = producer.lower()

        for keyword, definition in PRODUCER_FINDINGS.items():
            if keyword in normalized:
                return Finding(
                    severity=self._map_severity(definition.severity.value),
                    category=definition.category,
                    title=definition.title,
                    description=(
                        f"{definition.explanation}\n\n"
                        f"Natureza: {definition.nature}\n\n"
                        f"Impacto pericial: {definition.forensic_impact}"
                    ),
                    evidence_source="Producer/Creator/Software",
                    observed_value=producer,
                    recommendation=definition.recommendation,
                    score=0.90,
                )

        return None

    def _find_in_legacy_database(self, producer: str) -> Finding | None:
        producer_info = ProducerDatabase.find(producer)

        if not producer_info:
            return None

        severity = (
            Severity.WARNING
            if producer_info.risk_level.lower() == "atenção"
            else Severity.INFO
        )

        return Finding(
            severity=severity,
            category=producer_info.category,
            title=f"Vestígio de {producer_info.name}",
            description=(
                f"{producer_info.description} {producer_info.interpretation} "
                "Esse vestígio deve ser interpretado em conjunto com as datas, assinatura digital, "
                "estrutura do arquivo e contexto documental."
            ),
            evidence_source="Producer/Creator/Software",
            observed_value=producer,
            recommendation=(
                "Correlacionar com: "
                + ", ".join(producer_info.correlate_with[:5])
                + "."
            ),
            score=producer_info.confidence / 100,
        )

    def _missing_producer_finding(self) -> Finding:
        return Finding(
            severity=Severity.INFO,
            category="Metadados",
            title="Producer/Creator não identificado",
            description=(
                "Não foi identificado campo de Producer, Creator ou Software nos metadados. "
                "A ausência desse elemento não indica fraude por si só, mas limita a interpretação "
                "sobre a origem técnica e eventual processamento do arquivo."
            ),
            evidence_source="Metadados",
            observed_value="Ausente",
            recommendation=(
                "Correlacionar com estrutura do arquivo, datas internas, assinatura digital "
                "e eventual documento originário."
            ),
            score=0.70,
        )

    def _unknown_producer_finding(self, producer: str) -> Finding:
        return Finding(
            severity=Severity.INFO,
            category="Metadados",
            title="Producer/Creator não catalogado",
            description=(
                f"Foi identificado o produtor/creator '{producer}', porém ele ainda não consta "
                "na base de conhecimento do ForensiHash. Isso não indica irregularidade por si só, "
                "mas recomenda análise manual complementar."
            ),
            evidence_source="Producer/Creator/Software",
            observed_value=producer,
            recommendation="Cadastrar esse produtor na base de conhecimento caso seja recorrente.",
            score=0.60,
        )

    def _map_severity(self, severity: str) -> Severity:
        if severity == "critical":
            return Severity.CRITICAL

        if severity == "warning":
            return Severity.WARNING

        return Severity.INFO

    def _find_first(self, raw: dict, keys: list[str]) -> str | None:
        for key in keys:
            value = raw.get(key)
            if value:
                return str(value)

        return None
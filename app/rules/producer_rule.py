from app.enum.severity import Severity
from app.knowledge.producer_database import ProducerDatabase
from app.models import Finding, MetadataResult
from app.rules.base_rule import MetadataRule


class ProducerRule(MetadataRule):
    """Interpreta Producer/Creator/Software encontrados nos metadados."""

    def apply(self, metadata: MetadataResult) -> list[Finding]:
        findings: list[Finding] = []

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
            findings.append(
                Finding(
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
            )
            return findings

        producer_info = ProducerDatabase.find(producer)

        if producer_info:
            severity = (
                Severity.WARNING
                if producer_info.risk_level.lower() == "atenção"
                else Severity.INFO
            )

            findings.append(
                Finding(
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
            )
            return findings

        findings.append(
            Finding(
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
        )

        return findings

    def _find_first(self, raw: dict, keys: list[str]) -> str | None:
        for key in keys:
            value = raw.get(key)
            if value:
                return str(value)
        return None
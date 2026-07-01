from app.config.score_weights import METADATA_WEIGHT
from app.knowledge.producer_database import ProducerDatabase
from app.models import AnalysisResult, ScoreSection
from app.engines.score_evaluators.base_evaluator import BaseScoreEvaluator


class MetadataEvaluator(BaseScoreEvaluator):
    """Avalia existência, riqueza e utilidade técnica dos metadados."""

    def evaluate(self, result: AnalysisResult) -> ScoreSection:
        raw = result.metadata.raw if result.metadata else {}

        if not raw:
            return ScoreSection(
                name="Metadados",
                exists=False,
                score=0,
                weight=METADATA_WEIGHT,
                description="Não foram identificados metadados disponíveis para análise.",
                details=[
                    "A ausência de metadados limita a avaliação técnica da origem, temporalidade e processamento do arquivo."
                ],
            )

        points = 0
        max_points = 5
        details = []

        producer = self._find_first(
            raw,
            ["Producer", "PDF:Producer", "XMP:Producer", "Software", "Application"],
        )

        creator = self._find_first(
            raw,
            ["Creator", "PDF:Creator", "XMP:Creator", "GeneratingApplication"],
        )

        create_date = self._find_first(
            raw,
            ["CreateDate", "PDF:CreateDate", "XMP:CreateDate", "CreationDate"],
        )

        modify_date = self._find_first(
            raw,
            ["ModifyDate", "PDF:ModifyDate", "XMP:ModifyDate", "ModDate"],
        )

        if producer:
            points += 1
            details.append(f"✓ Producer identificado: {producer}")
        else:
            details.append("⚠ Producer não identificado.")

        if creator:
            points += 1
            details.append(f"✓ Creator identificado: {creator}")
        else:
            details.append("⚠ Creator não identificado.")

        if create_date:
            points += 1
            details.append(f"✓ Data de criação identificada: {create_date}")
        else:
            details.append("⚠ Data de criação não identificada.")

        if modify_date:
            points += 1
            details.append(f"✓ Data de modificação identificada: {modify_date}")
        else:
            details.append("⚠ Data de modificação não identificada.")

        producer_info = ProducerDatabase.find(producer or creator)

        if producer_info:
            points += 1
            details.append(
                f"✓ Produtor reconhecido na base: {producer_info.name} | {producer_info.risk_level}"
            )
        else:
            details.append("⚠ Produtor/creator ainda não reconhecido na base de conhecimento.")

        score = int((points / max_points) * 100)

        return ScoreSection(
            name="Metadados",
            exists=True,
            score=score,
            weight=METADATA_WEIGHT,
            description=f"Foram identificados {len(raw)} campo(s) de metadados. A pontuação considera campos essenciais e reconhecimento técnico do produtor.",
            details=details,
        )

    def _find_first(self, raw: dict, keys: list[str]) -> str | None:
        for key in keys:
            value = raw.get(key)

            if value:
                return str(value)

        return None
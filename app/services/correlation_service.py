from pathlib import Path
from typing import Sequence

from app.investigation.correlation_engine import (
    CorrelationEngine,
)
from app.investigation.correlation_result import (
    CorrelationResult,
)
from app.investigation.investigation_context_builder import (
    InvestigationContextBuilder,
)
from app.investigation.rules.embedded_hash_match_rule import (
    EmbeddedHashMatchRule,
)
from app.investigation.rules.embedded_hash_unmatched_rule import (
    EmbeddedHashUnmatchedRule,
)
from app.investigation.rules.entity_correlation_rule import EntityCorrelationRule
from app.investigation.rules.ip_context_rule import (
    IpContextRule,
)
from app.investigation.rules.json_context_rule import (
    JsonContextRule,
)
from app.investigation.rules.metadata_contract_date_rule import (
    MetadataContractDateRule,
)
from app.investigation.rules.ocr_context_rules import (
    OcrContextRule,
)
from app.investigation.rules.producer_context_rule import (
    ProducerContextRule,
)
from app.models import AnalysisResult
from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.investigation.case_correlation_index import CaseCorrelationIndex
from app.correlation.v2.pipeline import CanonicalCasePipeline, CanonicalCasePipelineResult


class CorrelationService:
    """
    Constrói o contexto investigativo e executa as regras
    de interpretação e correlação.
    """

    def __init__(self) -> None:
        self.context_builder = (
            InvestigationContextBuilder()
        )

        self.engine = CorrelationEngine(
            rules=[
                MetadataContractDateRule(),
                ProducerContextRule(),
                OcrContextRule(),
                JsonContextRule(),
                EntityCorrelationRule(),
                EmbeddedHashMatchRule(),
                EmbeddedHashUnmatchedRule(),
                IpContextRule(),
            ]
        )
        self._case_indexes: dict[str, CaseCorrelationIndex] = {}
        self.canonical_pipeline = CanonicalCasePipeline()

    def build_context(
        self,
        results: Sequence[AnalysisResult],
    ) -> InvestigationContext:
        """
        Constrói o contexto investigativo sem executar novamente
        OCR, análise de arquivos ou consultas externas.
        """

        return self.context_builder.build(
            results
        )

    def analyze(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        context = self.build_context(
            results
        )

        return self.engine.evaluate(
            context
        )

    def analyze_canonical(
        self, case_id: str, results: Sequence[AnalysisResult],
    ) -> CanonicalCasePipelineResult:
        """Canonical read model; legacy correlation remains during parity migration."""
        return self.canonical_pipeline.analyze(case_id, results)

    def update_case(
        self,
        case_id: str,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        """Substitui os membros do Caso e correlaciona resultados em cache."""
        index = self._case_index(case_id)
        return self.engine.evaluate(index.replace(results))

    def add_to_case(
        self,
        case_id: str,
        result: AnalysisResult,
    ) -> CorrelationResult:
        return self.engine.evaluate(self._case_index(case_id).add(result))

    def remove_from_case(
        self,
        case_id: str,
        file_path: Path | str,
    ) -> CorrelationResult:
        return self.engine.evaluate(self._case_index(case_id).remove(file_path))

    def _case_index(self, case_id: str) -> CaseCorrelationIndex:
        normalized = str(case_id).strip()
        if not normalized:
            raise ValueError("case_id must not be empty")
        index = self._case_indexes.get(normalized)
        if index is None:
            index = CaseCorrelationIndex(normalized, self.context_builder)
            self._case_indexes[normalized] = index
        return index

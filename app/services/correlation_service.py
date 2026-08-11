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

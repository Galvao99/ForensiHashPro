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
                EmbeddedHashMatchRule(),
                EmbeddedHashUnmatchedRule(),
                IpContextRule(),
            ]
        )

    def analyze(
        self,
        results: Sequence[AnalysisResult],
    ) -> CorrelationResult:
        context = self.context_builder.build(
            results
        )

        return self.engine.evaluate(
            context
        )
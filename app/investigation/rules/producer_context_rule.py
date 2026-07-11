from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule

from app.models.badge import (
    info_badge,
    neutral_badge,
    warning_badge,
)


class ProducerContextRule(BaseCorrelationRule):
    """
    Analisa os campos Producer e Creator
    identificados nos metadados do documento.
    """

    rule_id = "producer_context"

    name = "Producer / Creator"

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:

        findings: list[CorrelationFinding] = []

        for file_name in context.metadata_values.keys():

            producer = context.producers.get(
                file_name,
                "",
            )

            creator = context.creators.get(
                file_name,
                "",
            )

            if producer:

                self._analyze_producer(
                    findings=findings,
                    file_name=file_name,
                    producer=producer,
                )

            if creator:

                self._analyze_creator(
                    findings=findings,
                    file_name=file_name,
                    creator=creator,
                )

        return findings

    # ---------------------------------------------------------

    def _analyze_producer(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        producer: str,
    ) -> None:

        producer_lower = producer.lower()

        if "ghostscript" in producer_lower:

            self.add_warning(

                findings,

                title="Producer identificado",

                description=(
                    "Documento produzido utilizando Ghostscript."
                ),

                icon="producer",

                source_file=file_name,

                badges=[
                    warning_badge("Ghostscript"),
                    info_badge("Producer"),
                    neutral_badge(file_name),
                ],

                metadata={
                    "producer": producer,
                },

            )

            return

        if "aspose" in producer_lower:

            self.add_warning(

                findings,

                title="Producer identificado",

                description=(
                    "Documento produzido utilizando Aspose."
                ),

                icon="producer",

                source_file=file_name,

                badges=[
                    warning_badge("Aspose"),
                    info_badge("Producer"),
                    neutral_badge(file_name),
                ],

                metadata={
                    "producer": producer,
                },

            )

            return

        if "pdfium" in producer_lower:

            self.add_info(

                findings,

                title="Producer identificado",

                description="PDFium identificado.",

                icon="producer",

                source_file=file_name,

                badges=[
                    info_badge("PDFium"),
                    neutral_badge(file_name),
                ],

                metadata={
                    "producer": producer,
                },

            )

            return

        self.add_info(

            findings,

            title="Producer identificado",

            description="Producer localizado nos metadados.",

            icon="producer",

            source_file=file_name,

            badges=[
                info_badge(producer),
                neutral_badge(file_name),
            ],

            metadata={
                "producer": producer,
            },

        )

    # ---------------------------------------------------------

    def _analyze_creator(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        creator: str,
    ) -> None:

        self.add_info(

            findings,

            title="Creator identificado",

            description="Creator localizado nos metadados.",

            icon="creator",

            source_file=file_name,

            badges=[
                info_badge(creator),
                neutral_badge(file_name),
            ],

            metadata={
                "creator": creator,
            },

        )
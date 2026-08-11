from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.base_correlation_rule import BaseCorrelationRule
from app.models.badge import (
    info_badge,
    neutral_badge,
    success_badge,
)
from app.entities.models import EntityType


class OcrContextRule(BaseCorrelationRule):
    """
    Produz evidências visuais a partir dos textos extraídos
    de cada arquivo.

    A regra não realiza OCR diretamente. Ela interpreta os textos
    previamente extraídos e adicionados ao InvestigationContext.
    """

    rule_id = "ocr_context"
    name = "Contexto textual e OCR"

    def evaluate(
        self,
        context: InvestigationContext,
    ) -> list[CorrelationFinding]:
        findings: list[CorrelationFinding] = []

        for file_name, text in context.extracted_texts.items():
            normalized_text = text.strip()

            if not normalized_text:
                continue

            self._add_text_extraction_finding(
                findings=findings,
                file_name=file_name,
                text=normalized_text,
            )

            self._analyze_contract_date(
                findings=findings,
                context=context,
                file_name=file_name,
            )

            self._analyze_hashes(
                findings=findings,
                context=context,
                file_name=file_name,
            )

            self._analyze_resolved_entities(
                findings=findings,
                context=context,
                file_name=file_name,
            )

        return findings

    def _analyze_resolved_entities(
        self,
        *,
        findings: list[CorrelationFinding],
        context: InvestigationContext,
        file_name: str,
    ) -> None:
        entities = context.resolved_entities.get(file_name, [])
        by_type = {
            entity_type: [entity for entity in entities if entity.entity_type is entity_type]
            for entity_type in EntityType
        }

        for entity in by_type[EntityType.CPF]:
            self.add_ok(
                findings,
                title="CPF localizado no conteúdo",
                description="Foi identificado um CPF com checksum matematicamente válido.",
                icon="document-number",
                source_file=file_name,
                badges=[success_badge("CPF válido"), info_badge(self._format_cpf(entity.normalized_value)), neutral_badge(file_name)],
                metadata={"arquivo": file_name, "cpf": entity.normalized_value, "valido": True, "confidence": entity.confidence},
            )

        for entity_type, title, key, icon in (
            (EntityType.PHONE, "Telefone localizado no conteúdo", "telefones", "phone"),
            (EntityType.EMAIL, "E-mail localizado no conteúdo", "emails", "email"),
            (EntityType.DATETIME, "Datas localizadas no conteúdo", "datas", "calendar-search"),
            (EntityType.MONEY, "Valor monetário localizado no conteúdo", "valores", "money"),
            (EntityType.IP, "Endereço IP localizado no conteúdo", "enderecos_ip", "network"),
        ):
            selected = by_type[entity_type]
            if not selected:
                continue
            self.add_info(
                findings,
                title=title,
                description="Foram identificados fatos técnicos classificados pelo Entity Resolver V2.",
                icon=icon,
                source_file=file_name,
                badges=[info_badge(entity_type.value), neutral_badge(f"{len(selected)} encontrado(s)"), neutral_badge(file_name)],
                metadata={
                    "arquivo": file_name,
                    key: [entity.normalized_value for entity in selected],
                    "entities": [
                        {"normalized_value": entity.normalized_value, "confidence": entity.confidence}
                        for entity in selected
                    ],
                },
            )

        for entity_type, title in (
            (EntityType.AMBIGUOUS, "Entidade ambígua preservada"),
            (EntityType.UNKNOWN_NUMERIC_IDENTIFIER, "Identificador numérico não classificado"),
        ):
            for entity in by_type[entity_type]:
                self.add_info(
                    findings,
                    title=title,
                    description="A sequência foi preservada sem classificação arbitrária.",
                    icon="info",
                    source_file=file_name,
                    badges=[info_badge(entity_type.value), neutral_badge(file_name)],
                    metadata={
                        "arquivo": file_name,
                        "valor": entity.normalized_value,
                        "confidence": entity.confidence,
                        "hypotheses": [item.entity_type.value for item in entity.hypotheses],
                    },
                )

    def _add_text_extraction_finding(
        self,
        *,
        findings: list[CorrelationFinding],
        file_name: str,
        text: str,
    ) -> None:
        character_count = len(text)
        word_count = len(text.split())

        self.add_ok(
            findings,
            title="Conteúdo textual extraído",
            description=(
                "O arquivo apresentou conteúdo textual disponível "
                "para pesquisa e correlação."
            ),
            icon="ocr",
            source_file=file_name,
            badges=[
                success_badge("Texto extraído"),
                info_badge(f"{word_count} palavras"),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "quantidade_caracteres": character_count,
                "quantidade_palavras": word_count,
            },
        )

    def _analyze_contract_date(
        self,
        *,
        findings: list[CorrelationFinding],
        context: InvestigationContext,
        file_name: str,
    ) -> None:
        contract_date = context.contract_dates.get(file_name)

        if contract_date is None:
            return

        self.add_info(
            findings,
            title="Data de pactuação localizada",
            description=(
                "Foi identificada uma data contratual no conteúdo "
                "textual do documento."
            ),
            icon="calendar",
            source_file=file_name,
            badges=[
                info_badge("Data contratual"),
                success_badge(
                    contract_date.strftime("%d/%m/%Y")
                ),
                neutral_badge(file_name),
            ],
            metadata={
                "arquivo": file_name,
                "data_pactuacao": contract_date.isoformat(),
            },
        )

    def _analyze_hashes(
        self,
        *,
        findings: list[CorrelationFinding],
        context: InvestigationContext,
        file_name: str,
    ) -> None:
        hashes = context.declared_hashes.get(file_name, [])

        if not hashes:
            return

        for occurrence in hashes:

            self.add_info(
                findings,
                title="Hash localizado no conteúdo",
                description=(
                    "Foi identificado no corpo do documento um valor "
                    "com formato compatível com algoritmo de hash."
                ),
                icon="hash",
                source_file=file_name,
                badges=[
                    info_badge(occurrence.algorithm),
                    success_badge("Localizado no texto"),
                    neutral_badge(file_name),
                ],
                metadata={
                    "arquivo": file_name,
                    "algoritmo_provavel": occurrence.algorithm,
                    "hash": occurrence.value,
                    "declarado": occurrence.declared,
                },
            )

    def _format_cpf(
        self,
        cpf: str,
    ) -> str:
        if len(cpf) != 11:
            return cpf

        return (
            f"{cpf[:3]}."
            f"{cpf[3:6]}."
            f"{cpf[6:9]}-"
            f"{cpf[9:]}"
        )

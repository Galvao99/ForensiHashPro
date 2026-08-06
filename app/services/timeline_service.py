from datetime import datetime, timezone
from typing import Any

from app.models import AnalysisResult
from app.models.timeline_event import TimelineEvent
from app.services.contract_date_extractor import ContractDateExtractor
from app.services.contract_date_selector import ContractDateSelector
from app.services.text_extraction_service import TextExtractionService


class TimelineService:
    def __init__(self) -> None:
        self.text_service = TextExtractionService()
        self.date_extractor = ContractDateExtractor()
        self.date_selector = ContractDateSelector()

    def build_timeline(
        self,
        result: AnalysisResult,
    ) -> tuple[list[TimelineEvent], str]:
        events: list[TimelineEvent] = []

        metadata = result.metadata.raw
        file_info = result.file_info

        metadata_creation_date = self._get_metadata_date(
            metadata,
            ["CreateDate", "CreationDate", "FileCreateDate"],
        )

        metadata_modification_date = self._get_metadata_date(
            metadata,
            ["ModifyDate", "ModDate", "FileModifyDate", "MetadataDate"],
        )

        if metadata_creation_date:
            events.append(
                TimelineEvent(
                    title="Criação",
                    date=metadata_creation_date,
                    description="Criação do arquivo identificada nos metadados internos do documento.",
                    source="Metadados",
                    color="#6FA8DC",
                )
            )

        if metadata_modification_date:
            events.append(
                TimelineEvent(
                    title="Modificação",
                    date=metadata_modification_date,
                    description="Última modificação identificada nos metadados internos do documento.",
                    source="Metadados",
                    color="#E57373",
                    severity="warning",
                )
            )

        if file_info.created_at:
            events.append(
                TimelineEvent(
                    title="Criado no sistema",
                    date=file_info.created_at,
                    description="Data de criação do arquivo no sistema de arquivos local.",
                    source="Sistema de arquivos",
                    color="#93C5FD",
                )
            )

        if file_info.modified_at:
            events.append(
                TimelineEvent(
                    title="Modificado no sistema",
                    date=file_info.modified_at,
                    description="Data de modificação do arquivo no sistema de arquivos local.",
                    source="Sistema de arquivos",
                    color="#FCA5A5",
                    severity="warning",
                )
            )

        # O texto já foi extraído da cópia controlada durante a análise.
        # Reabrir o original aqui poderia misturar outro estado à timeline.
        text = result.extracted_text
        contract_date = self.date_selector.select(
            self.date_extractor.extract(text)
        )

        if contract_date:
            events.append(
                TimelineEvent(
                    title="Data contratual provável",
                    date=contract_date.extracted_date.value,
                    description=(
                        "Data identificada automaticamente no conteúdo textual do documento. "
                        "A classificação considera o contexto textual encontrado. "
                        "O OCR pode cometer erros de leitura e esta data deve ser confirmada pelo usuário."
                    ),
                    source="OCR / Texto",
                    color="#F6B26B",
                    severity="warning",
                    needs_confirmation=True,
                    confirmed=False,
                )
            )

        digital_signature_date = self._extract_digital_signature_date(
            result.digital_signature
        )

        if digital_signature_date:
            events.append(
                TimelineEvent(
                    title="Assinatura Digital",
                    date=digital_signature_date,
                    description="Data de assinatura digital identificada no documento.",
                    source="Assinatura Digital",
                    color="#B39DDB",
                )
            )

        opening_date = result.analyzed_at or datetime.now(timezone.utc)

        events.append(
            TimelineEvent(
                title="Abertura",
                date=opening_date,
                description="Arquivo aberto e analisado pelo ForensiHash.",
                source="ForensiHash",
                color="#81C784",
            )
        )

        # Instantes com timezone e valores declarados sem timezone não são
        # colocados na mesma escala cronológica. Cada grupo mantém ordenação
        # interna sem presumir um fuso para metadados ambíguos.
        events.sort(key=self._timeline_sort_key)

        result_text = self._analyze_timeline(
            metadata_creation_date=metadata_creation_date,
            metadata_modification_date=metadata_modification_date,
            system_created_at=file_info.created_at,
            system_modified_at=file_info.modified_at,
            contract_date=(
                contract_date.extracted_date.value
                if contract_date
                else None
            ),
            digital_signature_date=digital_signature_date,
            opening_date=opening_date,
        )

        return events, result_text

    def _analyze_timeline(
        self,
        metadata_creation_date: datetime | None,
        metadata_modification_date: datetime | None,
        system_created_at: datetime | None,
        system_modified_at: datetime | None,
        contract_date: datetime | None,
        digital_signature_date: datetime | None,
        opening_date: datetime,
    ) -> str:
        alerts: list[str] = []

        if self._comparable(metadata_creation_date, contract_date) and metadata_creation_date > contract_date:
            alerts.append(
                "a criação interna do documento é posterior à data contratual identificada"
            )

        if self._comparable(metadata_modification_date, contract_date) and metadata_modification_date > contract_date:
            alerts.append(
                "a modificação interna do documento é posterior à data contratual identificada"
            )

        if self._comparable(metadata_creation_date, digital_signature_date) and metadata_creation_date > digital_signature_date:
            alerts.append(
                "a criação interna do documento é posterior à assinatura digital identificada"
            )

        if self._comparable(metadata_modification_date, digital_signature_date) and metadata_modification_date > digital_signature_date:
            alerts.append(
                "a modificação interna do documento é posterior à assinatura digital identificada"
            )

        if self._comparable(contract_date, digital_signature_date) and contract_date > digital_signature_date:
            alerts.append(
                "a data contratual identificada é posterior à assinatura digital"
            )

        if self._comparable(system_created_at, metadata_creation_date) and system_created_at < metadata_creation_date:
            alerts.append(
                "a data de criação no sistema de arquivos é anterior à data de criação interna do documento"
            )

        if self._comparable(system_modified_at, metadata_modification_date) and system_modified_at < metadata_modification_date:
            alerts.append(
                "a data de modificação no sistema de arquivos é anterior à modificação interna do documento"
            )

        if self._comparable(digital_signature_date, opening_date) and digital_signature_date > opening_date:
            alerts.append(
                "a assinatura digital é posterior à data de abertura/análise pelo ForensiHash"
            )

        if not alerts:
            return (
                "Resultado: A linha temporal apresenta coerência entre os elementos "
                "extraídos dos metadados, do conteúdo textual do documento, da assinatura "
                "digital, do sistema de arquivos e da abertura do arquivo para análise."
            )

        return (
            "Resultado: A linha temporal apresenta inconsistência, pois "
            + "; ".join(alerts)
            + "."
        )

    @staticmethod
    def _comparable(left: datetime | None, right: datetime | None) -> bool:
        if left is None or right is None:
            return False
        return (left.tzinfo is None) == (right.tzinfo is None)

    @staticmethod
    def _timeline_sort_key(event: TimelineEvent) -> tuple[int, datetime]:
        assert event.date is not None
        aware = event.date.tzinfo is not None
        return (1 if aware else 0, event.date.replace(tzinfo=None))

    def _extract_digital_signature_date(self, digital_signature: Any) -> datetime | None:
        if not digital_signature:
            return None

        possible_attrs = [
            "signature_date",
            "signed_at",
            "signing_time",
            "timestamp",
            "timestamp_date",
            "date",
        ]

        for attr in possible_attrs:
            value = getattr(digital_signature, attr, None)

            parsed = self._parse_any_date(value)

            if parsed:
                return parsed

        return None

    def _get_metadata_date(
        self,
        metadata: dict[str, Any],
        keys: list[str],
    ) -> datetime | None:
        for key in keys:
            value = metadata.get(key)

            parsed = self._parse_any_date(value)

            if parsed:
                return parsed

        return None

    def _parse_any_date(self, value: Any) -> datetime | None:
        if not value:
            return None

        if isinstance(value, datetime):
            return value

        return self._parse_metadata_date(str(value))

    def _parse_metadata_date(self, value: str) -> datetime | None:
        value = value.strip()
        value = value.replace("Z", "").strip()

        if value.startswith("D:"):
            value = value[2:]

        if len(value) >= 14 and value[:14].isdigit():
            try:
                return datetime.strptime(value[:14], "%Y%m%d%H%M%S")
            except ValueError:
                pass

        formats = [
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue

        return None

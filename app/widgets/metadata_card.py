from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.knowledge.producer_database import ProducerDatabase
from app.models import MetadataResult
from app.widgets.metadata_table import MetadataTable


class MetadataCard(QWidget):
    """Card visual para exibição e interpretação inicial dos metadados."""

    def __init__(self) -> None:
        super().__init__()

        self.title_label = QLabel("🧬 Metadados")
        self.title_label.setObjectName("metadataCardTitle")

        self.count_label = QLabel("0 campos")
        self.count_label.setObjectName("metadataCountLabel")
        self.count_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.producer_label = QLabel("Producer: não identificado")
        self.producer_label.setObjectName("metadataHighlightText")
        self.producer_label.setWordWrap(True)

        self.category_label = QLabel("Categoria: não identificada")
        self.category_label.setObjectName("metadataHighlightText")
        self.category_label.setWordWrap(True)

        self.created_label = QLabel("Criação: não identificada")
        self.created_label.setObjectName("metadataHighlightText")
        self.created_label.setWordWrap(True)

        self.modified_label = QLabel("Modificação: não identificada")
        self.modified_label.setObjectName("metadataHighlightText")
        self.modified_label.setWordWrap(True)

        self.insight_label = QLabel(
            "Os metadados serão exibidos após a análise do arquivo."
        )
        self.insight_label.setObjectName("metadataInsightText")
        self.insight_label.setWordWrap(True)

        self.table = MetadataTable()

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("metadataCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(12)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.count_label)

        highlights = QFrame()
        highlights.setObjectName("metadataHighlightsBox")

        highlights_layout = QVBoxLayout(highlights)
        highlights_layout.setContentsMargins(12, 10, 12, 10)
        highlights_layout.setSpacing(6)

        highlights_layout.addWidget(self.producer_label)
        highlights_layout.addWidget(self.category_label)
        highlights_layout.addWidget(self.created_label)
        highlights_layout.addWidget(self.modified_label)

        insight_box = QFrame()
        insight_box.setObjectName("metadataInsightBox")

        insight_layout = QVBoxLayout(insight_box)
        insight_layout.setContentsMargins(12, 10, 12, 10)

        insight_title = QLabel("💡 Insight técnico")
        insight_title.setObjectName("metadataInsightTitle")

        insight_layout.addWidget(insight_title)
        insight_layout.addWidget(self.insight_label)

        card_layout.addLayout(header)
        card_layout.addWidget(highlights)
        card_layout.addWidget(insight_box)
        card_layout.addWidget(self.table)

        main_layout.addWidget(card)

    def update_metadata(self, metadata: MetadataResult) -> None:
        raw = metadata.raw if metadata else {}

        self.count_label.setText(f"{len(raw)} campos")
        self.table.update_metadata(metadata)

        producer_value = self._find_first(
            raw,
            [
                "Producer",
                "producer",
                "PDF:Producer",
                "XMP:Producer",
                "Creator",
                "creator",
                "Software",
                "software",
                "Application",
                "GeneratingApplication",
            ],
        )

        created = self._find_first(
            raw,
            [
                "CreateDate",
                "created_at",
                "CreationDate",
                "PDF:CreateDate",
                "XMP:CreateDate",
                "DateCreated",
            ],
        )

        modified = self._find_first(
            raw,
            [
                "ModifyDate",
                "modified_at",
                "ModDate",
                "PDF:ModifyDate",
                "XMP:ModifyDate",
                "DateModified",
            ],
        )

        producer_info = ProducerDatabase.find(producer_value)

        if producer_value:
            self.producer_label.setText(f"Producer/Creator: {producer_value}")
        else:
            self.producer_label.setText("Producer/Creator: não identificado")

        if producer_info:
            self.category_label.setText(
                f"Categoria: {producer_info.category} • Confiança {producer_info.confidence}% • {producer_info.risk_level}"
            )
            self.insight_label.setText(self._build_database_insight(producer_info))
        else:
            self.category_label.setText("Categoria: não identificada")
            self.insight_label.setText(self._build_generic_insight(producer_value, created, modified))

        self.created_label.setText(
            f"Criação: {created}" if created else "Criação: não identificada"
        )
        self.modified_label.setText(
            f"Modificação: {modified}" if modified else "Modificação: não identificada"
        )

    def _find_first(self, raw: dict, keys: list[str]) -> str | None:
        for key in keys:
            value = raw.get(key)
            if value:
                return str(value)
        return None

    def _build_database_insight(self, producer_info) -> str:
        common_uses = ", ".join(producer_info.common_uses[:4])
        correlate_with = ", ".join(producer_info.correlate_with[:5])

        return (
            f"{producer_info.description} {producer_info.interpretation} "
            f"Usos comuns: {common_uses}. "
            f"Correlacionar com: {correlate_with}."
        )

    def _build_generic_insight(
        self,
        producer_value: str | None,
        created: str | None,
        modified: str | None,
    ) -> str:
        if not producer_value:
            return (
                "Não foi identificado campo de Producer, Creator ou Software. "
                "A ausência desses metadados pode limitar a interpretação da origem técnica do arquivo."
            )

        if created and modified and created != modified:
            return (
                "Foram identificados registros distintos de criação e modificação. "
                "Recomenda-se avaliar a coerência temporal desses campos com o contexto do documento."
            )

        return (
            "O produtor/creator foi identificado, porém ainda não consta na base de conhecimento. "
            "Recomenda-se cadastrar este vestígio para ampliar a interpretação técnica do ForensiHash."
        )
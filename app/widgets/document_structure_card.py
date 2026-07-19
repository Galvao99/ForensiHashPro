from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.knowledge.pdf_structure_concepts import get_pdf_structure_concept
from app.models.pdf_raw_analysis_result import PdfRawAnalysisResult
from app.widgets.base_card import BaseCard
from app.widgets.concept_explanation_panel import ConceptExplanationPanel
from app.widgets.finding_card import FindingCard
from app.widgets.flow_layout import FlowLayout
from app.widgets.technical_metric_badge import TechnicalMetricBadge


class DocumentStructureCard(BaseCard):
    """Apresenta fatos estruturais já produzidos pelo parser de PDF."""

    FEATURES = (
        ("JavaScript", "has_javascript", "javascript"),
        ("Criptografia", "encrypted", "encryption"),
        ("Arquivos incorporados", "has_embedded_files", "embedded_files"),
        ("OpenAction", "has_open_action", "open_action"),
        ("Additional Actions", "has_additional_actions", "additional_actions"),
        ("AcroForm", "has_acroform", "acroform"),
        ("XFA", "has_xfa", "xfa"),
    )

    def __init__(self) -> None:
        super().__init__("Estrutura do Documento")
        self._selected_badge: TechnicalMetricBadge | None = None
        self._badges: list[TechnicalMetricBadge] = []

        self.empty_label = QLabel(
            "Análise estrutural não disponível para este arquivo."
        )
        self.empty_label.setObjectName("CardContent")
        self.empty_label.setWordWrap(True)

        self.content = QWidget()
        self.content.setObjectName("DocumentStructureContent")
        content_layout = QVBoxLayout(self.content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)

        self.summary_layout = FlowLayout()
        self.features_layout = FlowLayout()
        self.explanation_panel = ConceptExplanationPanel()
        self.explanation_panel.close_requested.connect(self._close_explanation)
        self.findings_layout = QVBoxLayout()
        self.findings_layout.setSpacing(9)

        content_layout.addWidget(self._section_title("Resumo estrutural"))
        content_layout.addLayout(self.summary_layout)
        content_layout.addWidget(self._section_title("Recursos analisados"))
        content_layout.addLayout(self.features_layout)
        content_layout.addWidget(self.explanation_panel)
        content_layout.addWidget(self._section_title("Findings estruturais"))
        content_layout.addLayout(self.findings_layout)

        self.body_layout.addWidget(self.empty_label)
        self.body_layout.addWidget(self.content)
        self.content.setVisible(False)

    @property
    def selected_concept_key(self) -> str | None:
        return self._selected_badge.concept_key if self._selected_badge else None

    @property
    def badges(self) -> tuple[TechnicalMetricBadge, ...]:
        return tuple(self._badges)

    def update_result(self, result: PdfRawAnalysisResult | None) -> None:
        self._close_explanation()
        self._clear_layout(self.summary_layout)
        self._clear_layout(self.features_layout)
        self._clear_layout(self.findings_layout)
        self._badges.clear()

        self.empty_label.setVisible(result is None)
        self.content.setVisible(result is not None)
        if result is None:
            return

        summary = (
            (result.version or "Não identificada", "PDF", "pdf_version"),
            (
                str(len(result.objects)),
                self._plural(len(result.objects), "objeto", "objetos"),
                "objects",
            ),
            (
                str(result.stream_count),
                self._plural(result.stream_count, "stream", "streams"),
                "streams",
            ),
            (
                str(len(result.trailer_offsets)),
                self._plural(
                    len(result.trailer_offsets), "trailer", "trailers"
                ),
                "trailer",
            ),
            (str(len(result.startxrefs)), "startxref", "startxref"),
            (str(len(result.eof_offsets)), "%%EOF", "eof"),
        )
        for value, label, key in summary:
            self._add_badge(
                self.summary_layout,
                value,
                label,
                key,
                label_first=key == "pdf_version",
            )

        for label, attribute, key in self.FEATURES:
            detected = bool(getattr(result, attribute))
            self._add_badge(
                self.features_layout,
                "detectado" if detected else "não detectado",
                label,
                key,
                detected,
                label_first=True,
            )

        if result.findings:
            for finding in result.findings:
                self.findings_layout.addWidget(FindingCard(finding))
        else:
            label = QLabel("Nenhum finding estrutural foi produzido.")
            label.setObjectName("StructureMutedText")
            self.findings_layout.addWidget(label)

    def _add_badge(
        self,
        layout: FlowLayout,
        value: str,
        label: str,
        concept_key: str,
        detected: bool | None = None,
        label_first: bool = False,
    ) -> None:
        badge = TechnicalMetricBadge(
            value,
            label,
            concept_key,
            detected,
            label_first,
        )
        badge.concept_requested.connect(
            lambda _key, item=badge: self._toggle_concept(item)
        )
        self._badges.append(badge)
        layout.addWidget(badge)

    def _toggle_concept(self, badge: TechnicalMetricBadge) -> None:
        if self._selected_badge is badge:
            self._close_explanation()
            return
        if self._selected_badge is not None:
            self._selected_badge.setChecked(False)
        self._selected_badge = badge
        badge.setChecked(True)
        self.explanation_panel.show_concept(
            get_pdf_structure_concept(badge.concept_key)
        )

    def _close_explanation(self) -> None:
        if self._selected_badge is not None:
            self._selected_badge.setChecked(False)
        self._selected_badge = None
        self.explanation_panel.clear()

    @staticmethod
    def _plural(count: int, singular: str, plural: str) -> str:
        return singular if count == 1 else plural

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("StructureSectionTitle")
        return label

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                DocumentStructureCard._clear_layout(child_layout)

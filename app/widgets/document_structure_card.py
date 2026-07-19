from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from app.knowledge.pdf_structure_concepts import get_pdf_structure_concept
from app.models.pdf_raw_analysis_result import PdfRawAnalysisResult
from app.presentation.pdf_raw_technical_formatter import PdfRawTechnicalFormatter
from app.widgets.base_card import BaseCard
from app.widgets.concept_explanation_panel import ConceptExplanationPanel
from app.widgets.finding_card import FindingCard
from app.widgets.flow_layout import FlowLayout
from app.widgets.technical_metric_badge import TechnicalMetricBadge
from app.widgets.raw_technical_data_panel import RawTechnicalDataPanel


class DocumentStructureCard(BaseCard):
    """Apresenta fatos estruturais já produzidos pelo parser de PDF."""

    FEATURES = (
        ("JavaScript", "has_javascript", "javascript"),
        ("Encrypt", "encrypted", "encryption"),
        ("EmbeddedFile", "has_embedded_files", "embedded_files"),
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

        self.raw_formatter = PdfRawTechnicalFormatter()
        self._raw_technical_text = ""

        self.summary_layout = FlowLayout()
        self.features_layout = FlowLayout()
        self.explanation_panel = ConceptExplanationPanel()
        self.explanation_panel.close_requested.connect(self._close_explanation)
        self.interaction_hint = QLabel(
            "Selecione um item para visualizar sua definição técnica."
        )
        self.interaction_hint.setObjectName("StructureInteractionHint")
        self.interaction_hint.setWordWrap(True)
        self.findings_layout = QVBoxLayout()
        self.findings_layout.setSpacing(9)

        self.raw_toggle_button = QPushButton("Examinar estrutura técnica")
        self.raw_toggle_button.setObjectName("RawTechnicalToggleButton")
        self.raw_toggle_button.setCheckable(True)
        self.raw_toggle_button.setCursor(Qt.PointingHandCursor)
        self.raw_toggle_button.clicked.connect(self._toggle_raw_panel)
        self.raw_panel = RawTechnicalDataPanel()
        self.raw_panel.close_requested.connect(self._close_raw_panel)

        content_layout.addWidget(self._section_title("Resumo estrutural"))
        content_layout.addLayout(self.summary_layout)
        content_layout.addWidget(self._section_title("Recursos analisados"))
        content_layout.addLayout(self.features_layout)
        content_layout.addWidget(self.interaction_hint)
        content_layout.addWidget(self.explanation_panel)
        content_layout.addWidget(self._section_title("Findings estruturais"))
        content_layout.addLayout(self.findings_layout)
        content_layout.addWidget(
            self.raw_toggle_button,
            alignment=Qt.AlignLeft,
        )
        content_layout.addWidget(self.raw_panel)

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
        self._reset_raw_panel()
        self._clear_layout(self.summary_layout)
        self._clear_layout(self.features_layout)
        self._clear_layout(self.findings_layout)
        self._badges.clear()

        self.empty_label.setVisible(result is None)
        self.content.setVisible(result is not None)
        if result is None:
            return

        self._raw_technical_text = self.raw_formatter.format(result)
        self.raw_panel.set_text(self._raw_technical_text)

        summary = (
            (
                f"PDF {result.version}" if result.version else "Não identificada",
                "Versão",
                "pdf_version",
            ),
            (
                str(len(result.objects)),
                self._plural(len(result.objects), "Objeto", "Objetos"),
                "objects",
            ),
            (
                str(result.stream_count),
                self._plural(result.stream_count, "Stream", "Streams"),
                "streams",
            ),
            (
                str(len(result.trailer_offsets)),
                self._plural(
                    len(result.trailer_offsets), "Trailer", "Trailers"
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
            )

        for label, attribute, key in self.FEATURES:
            detected = bool(getattr(result, attribute))
            self._add_badge(
                self.features_layout,
                "Detectado" if detected else "Não detectado",
                label,
                key,
                detected,
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

    def _toggle_raw_panel(self, checked: bool) -> None:
        if checked:
            self.raw_panel.open_panel()
            self.raw_toggle_button.setText("Ocultar estrutura técnica")
        else:
            self.raw_panel.close_panel()
            self.raw_toggle_button.setText("Examinar estrutura técnica")

    def _close_raw_panel(self) -> None:
        self.raw_toggle_button.setChecked(False)
        self.raw_toggle_button.setText("Examinar estrutura técnica")
        self.raw_panel.close_panel()

    def _reset_raw_panel(self) -> None:
        self._raw_technical_text = ""
        self.raw_toggle_button.setChecked(False)
        self.raw_toggle_button.setText("Examinar estrutura técnica")
        self.raw_panel.clear()

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

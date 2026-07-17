from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.badge import neutral_badge
from app.models.pdf_raw_analysis_result import PdfRawAnalysisResult
from app.widgets.badge_widget import BadgeWidget
from app.widgets.base_card import BaseCard
from app.widgets.finding_card import FindingCard


class DocumentStructureCard(BaseCard):
    """Apresenta fatos estruturais já produzidos pelo parser de PDF."""

    FEATURES = (
        ("JavaScript", "has_javascript"),
        ("Encrypt", "encrypted"),
        ("Embedded Files", "has_embedded_files"),
        ("OpenAction", "has_open_action"),
        ("Additional Actions", "has_additional_actions"),
        ("AcroForm", "has_acroform"),
        ("XFA", "has_xfa"),
    )

    def __init__(self) -> None:
        super().__init__("Estrutura do Documento")

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

        self.summary_grid = QGridLayout()
        self.summary_grid.setHorizontalSpacing(24)
        self.summary_grid.setVerticalSpacing(8)

        self.features_layout = QHBoxLayout()
        self.features_layout.setSpacing(7)

        self.offsets_grid = QGridLayout()
        self.offsets_grid.setHorizontalSpacing(24)
        self.offsets_grid.setVerticalSpacing(7)

        self.findings_layout = QVBoxLayout()
        self.findings_layout.setSpacing(9)

        content_layout.addWidget(self._section_title("Resumo estrutural"))
        content_layout.addLayout(self.summary_grid)
        content_layout.addWidget(self._section_title("Recursos detectados"))
        content_layout.addLayout(self.features_layout)
        content_layout.addWidget(self._section_title("Offsets relevantes"))
        content_layout.addLayout(self.offsets_grid)
        content_layout.addWidget(self._section_title("Findings estruturais"))
        content_layout.addLayout(self.findings_layout)

        self.body_layout.addWidget(self.empty_label)
        self.body_layout.addWidget(self.content)
        self.content.setVisible(False)

    def update_result(self, result: PdfRawAnalysisResult | None) -> None:
        self._clear_layout(self.summary_grid)
        self._clear_layout(self.features_layout)
        self._clear_layout(self.offsets_grid)
        self._clear_layout(self.findings_layout)

        self.empty_label.setVisible(result is None)
        self.content.setVisible(result is not None)
        if result is None:
            return

        summary = (
            ("Versão do PDF", result.version or "Não identificada"),
            ("Objetos", str(len(result.objects))),
            ("Streams", str(result.stream_count)),
            ("Trailers", str(len(result.trailer_offsets))),
            ("Startxref", str(len(result.startxrefs))),
            ("Marcadores EOF", str(len(result.eof_offsets))),
        )
        for index, (label, value) in enumerate(summary):
            self._add_value(self.summary_grid, index, label, value, 2)

        detected = [
            label
            for label, attribute in self.FEATURES
            if getattr(result, attribute)
        ]
        if detected:
            for label in detected:
                self.features_layout.addWidget(
                    BadgeWidget(neutral_badge(label))
                )
            self.features_layout.addStretch()
        else:
            label = QLabel("Nenhum dos recursos listados foi detectado.")
            label.setObjectName("StructureMutedText")
            self.features_layout.addWidget(label)
            self.features_layout.addStretch()

        offsets = (
            ("Header", self._format_offsets([result.header_offset])),
            ("Trailer", self._format_offsets(result.trailer_offsets)),
            (
                "StartXref",
                self._format_offsets(
                    item.marker_offset for item in result.startxrefs
                ),
            ),
            ("EOF", self._format_offsets(result.eof_offsets)),
        )
        for index, (label, value) in enumerate(offsets):
            self._add_value(self.offsets_grid, index, label, value, 1)

        if result.findings:
            for finding in result.findings:
                self.findings_layout.addWidget(FindingCard(finding))
        else:
            label = QLabel("Nenhum finding estrutural foi produzido.")
            label.setObjectName("StructureMutedText")
            self.findings_layout.addWidget(label)

    @staticmethod
    def _section_title(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("StructureSectionTitle")
        return label

    @staticmethod
    def _add_value(
        layout: QGridLayout,
        index: int,
        label: str,
        value: str,
        columns: int,
    ) -> None:
        row, column = divmod(index, columns)
        container = QWidget()
        container.setObjectName("StructureValue")
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        value_layout = QHBoxLayout(container)
        value_layout.setContentsMargins(0, 0, 0, 0)
        key_label = QLabel(f"{label}:")
        key_label.setObjectName("StructureValueLabel")
        value_label = QLabel(value)
        value_label.setObjectName("StructureValueText")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setWordWrap(True)
        value_layout.addWidget(key_label)
        value_layout.addWidget(value_label, stretch=1)
        layout.addWidget(container, row, column)

    @staticmethod
    def _format_offsets(offsets: Iterable[int | None]) -> str:
        values = [f"0x{offset:X}" for offset in offsets if offset is not None]
        return ", ".join(values) if values else "Não identificado"

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            child_layout = item.layout()
            if widget is not None:
                widget.deleteLater()
            elif child_layout is not None:
                DocumentStructureCard._clear_layout(child_layout)

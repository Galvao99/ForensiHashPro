from __future__ import annotations

from collections.abc import Iterable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.models.digital_signature_result import SignatureAnalysisStatus


class TechnicalField(QWidget):
    def __init__(self, label: str, value: str, *, mono: bool = False) -> None:
        super().__init__()
        name = QLabel(label.upper())
        name.setObjectName("TechnicalFieldLabel")
        self.value = QLabel(value)
        self.value.setObjectName("TechnicalFieldMono" if mono else "TechnicalFieldValue")
        self.value.setWordWrap(True)
        self.value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)
        layout.addWidget(name)
        layout.addWidget(self.value)


class SummarySection(QFrame):
    def __init__(self, title: str, fields: Iterable[tuple[str, str, bool]]) -> None:
        super().__init__()
        self.setObjectName("SummarySection")
        title_label = QLabel(title.upper())
        title_label.setObjectName("SummarySectionTitle")
        fields_layout = QGridLayout()
        fields_layout.setContentsMargins(0, 0, 0, 0)
        fields_layout.setHorizontalSpacing(18)
        fields_layout.setVerticalSpacing(12)
        for index, (label, value, mono) in enumerate(fields):
            fields_layout.addWidget(TechnicalField(label, value, mono=mono), index // 2, index % 2)
        fields_layout.setColumnStretch(0, 1)
        fields_layout.setColumnStretch(1, 1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)
        layout.addWidget(title_label)
        layout.addLayout(fields_layout)


class ForensicSummary(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self._sections: list[SummarySection] = []
        self._compact = False
        self.sections_layout = QGridLayout(self)
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(12)

    def update_analysis(self, result: AnalysisResult) -> None:
        self._clear()
        magic = result.magic_numbers
        structure = result.pdf_structure
        metadata = result.metadata.raw
        sections = [
            SummarySection("Identificação", [
                ("Formato", magic.detected_format or magic.detected_type or "Não identificado", False),
                ("MIME", magic.mime_type or "Não disponível", True),
                ("Tamanho", self._format_size(result.file_info.size_bytes), False),
                ("Magic number", "Compatível com a extensão" if magic.extension_matches else "Divergência reportada", False),
            ]),
            SummarySection("Estrutura", self._structure_fields(result)),
            SummarySection("Metadados relevantes", self._metadata_fields(metadata)),
            SummarySection("Assinaturas", [
                ("Estado", self._signature_text(result.digital_signature.analysis_status), False),
                ("Quantidade reportada", str(result.digital_signature.signature_count), False),
            ]),
        ]
        if structure is None and magic.detected_format.upper() != "PDF":
            sections[1] = SummarySection("Estrutura", [("Estado", "Detalhes disponíveis na página técnica correspondente.", False)])
        self._sections = sections
        self._reflow()

    def set_compact(self, compact: bool) -> None:
        if compact != self._compact:
            self._compact = compact
            self._reflow()

    def _reflow(self) -> None:
        columns = 1 if self._compact else 2
        for section in self._sections:
            self.sections_layout.removeWidget(section)
        for index, section in enumerate(self._sections):
            self.sections_layout.addWidget(section, index // columns, index % columns)
        self.sections_layout.setColumnStretch(0, 1)
        self.sections_layout.setColumnStretch(1, 0 if self._compact else 1)

    def _structure_fields(self, result: AnalysisResult) -> list[tuple[str, str, bool]]:
        structure = result.pdf_structure
        if structure is None:
            status = "Estrutura compatível nos critérios verificados" if result.integrity.is_structurally_valid else "Observações estruturais disponíveis"
            return [("Estado", status, False), ("Revisões", str(result.integrity.incremental_updates), False)]
        return [
            ("Versão PDF", structure.pdf_version or "Não reportada", False),
            ("Objetos", str(structure.object_count), False),
            ("Streams", str(structure.stream_count), False),
            ("Revisões incrementais", str(structure.incremental_updates), False),
        ]

    @staticmethod
    def _metadata_fields(metadata: dict) -> list[tuple[str, str, bool]]:
        preferred = ("CreateDate", "ModifyDate", "Producer", "Creator", "Author")
        values: list[tuple[str, str, bool]] = []
        for preferred_key in preferred:
            match = next((value for key, value in metadata.items() if key.split(":")[-1] == preferred_key), None)
            if match not in (None, ""):
                values.append((preferred_key, str(match), preferred_key.endswith("Date")))
            if len(values) == 4:
                break
        return values or [("Estado", "Nenhum metadado relevante reportado.", False)]

    @staticmethod
    def _signature_text(status: SignatureAnalysisStatus | None) -> str:
        return {
            SignatureAnalysisStatus.PRESENT: "Assinatura incorporada reportada.",
            SignatureAnalysisStatus.ABSENT: "Nenhuma assinatura incorporada reportada.",
            SignatureAnalysisStatus.NOT_APPLICABLE: "Análise não aplicável ao formato.",
            SignatureAnalysisStatus.UNSUPPORTED: "Formato não suportado para esta verificação.",
            SignatureAnalysisStatus.ERROR: "Não foi possível concluir a verificação.",
        }.get(status, "Verificação não executada.")

    @staticmethod
    def _format_size(size: int) -> str:
        value = float(size)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or unit == "TB":
                return f"{int(value)} {unit}" if unit == "B" else f"{value:.2f} {unit}"
            value /= 1024
        return f"{size} B"

    def _clear(self) -> None:
        while self.sections_layout.count():
            item = self.sections_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        self._sections = []

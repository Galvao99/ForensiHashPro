from pathlib import Path

from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.engines.comparison_engine import ComparisonEngine
from app.models.comparison_result import ComparisonResult
from app.services.analysis_service import AnalysisService
from app.widgets.comparison_card import ComparisonCard


class ComparisonWorkspace(QWidget):
    """Área dedicada à comparação forense entre dois arquivos."""

    def __init__(self, analysis_service: AnalysisService) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.comparison_engine = ComparisonEngine()

        self.left_result = None
        self.right_result = None
        self.comparison_result: ComparisonResult | None = None

        self.title = QLabel("Comparação Forense")
        self.title.setObjectName("PageTitle")

        self.left_label = QLabel("Arquivo A: não selecionado")
        self.left_label.setObjectName("CardContent")

        self.right_label = QLabel("Arquivo B: não selecionado")
        self.right_label.setObjectName("CardContent")

        self.select_left_button = QPushButton("📄 Escolher Arquivo A")
        self.select_right_button = QPushButton("📄 Escolher Arquivo B")
        self.clear_button = QPushButton("🧹 Limpar comparação")

        self.select_left_button.clicked.connect(self.select_left_file)
        self.select_right_button.clicked.connect(self.select_right_file)
        self.clear_button.clicked.connect(self.clear_comparison)

        self.score_label = QLabel("Score de compatibilidade: 0%")
        self.score_label.setObjectName("DashboardTitle")

        self.score_bar = QProgressBar()
        self.score_bar.setRange(0, 100)
        self.score_bar.setValue(0)
        self.score_bar.setTextVisible(True)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("ComparisonInnerTabs")

        self.general_card = ComparisonCard("📊 Geral")
        self.hash_card = ComparisonCard("🔐 Hashes")
        self.metadata_card = ComparisonCard("📑 Metadados")
        self.magic_card = ComparisonCard("🧬 Magic Number")
        self.signature_card = ComparisonCard("🔏 Assinatura Digital")
        self.findings_card = ComparisonCard("⚠ Vestígios")

        self.tabs.addTab(self.general_card, "Geral")
        self.tabs.addTab(self.hash_card, "Hashes")
        self.tabs.addTab(self.metadata_card, "Metadados")
        self.tabs.addTab(self.magic_card, "Magic Number")
        self.tabs.addTab(self.signature_card, "Assinatura Digital")
        self.tabs.addTab(self.findings_card, "Vestígios")

        self._build_layout()

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout()
        root_layout.setSpacing(16)

        file_layout = QHBoxLayout()

        left_layout = QVBoxLayout()
        left_layout.addWidget(self.left_label)
        left_layout.addWidget(self.select_left_button)

        right_layout = QVBoxLayout()
        right_layout.addWidget(self.right_label)
        right_layout.addWidget(self.select_right_button)

        file_layout.addLayout(left_layout)
        file_layout.addLayout(right_layout)

        root_layout.addWidget(self.title)
        root_layout.addLayout(file_layout)
        root_layout.addWidget(self.score_label)
        root_layout.addWidget(self.score_bar)
        root_layout.addWidget(self.tabs, stretch=1)
        root_layout.addWidget(self.clear_button)

        self.setLayout(root_layout)

    def select_left_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo A",
        )

        if not filename:
            return

        self.left_result = self.analysis_service.analyze(Path(filename))
        self.left_label.setText(f"Arquivo A: {self.left_result.file_info.name}")
        self.try_compare()

    def select_right_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo B",
        )

        if not filename:
            return

        self.right_result = self.analysis_service.analyze(Path(filename))
        self.right_label.setText(f"Arquivo B: {self.right_result.file_info.name}")
        self.try_compare()

    def try_compare(self) -> None:
        if self.left_result is None or self.right_result is None:
            return

        self.comparison_result = self.comparison_engine.compare(
            self.left_result,
            self.right_result,
        )

        self.update_dashboard(self.comparison_result)

    def update_dashboard(self, result: ComparisonResult) -> None:
        score = self.calculate_score(result)

        self.score_bar.setValue(score)
        self.score_label.setText(f"Score de compatibilidade: {score}%")

        self.general_card.update_text(self._format_general(result))
        self.hash_card.update_text(self._format_section(result, "SHA-256"))
        self.magic_card.update_text(self._format_section(result, "Magic Number"))
        self.signature_card.update_text(
            self._format_section(result, "Assinatura Digital")
        )

        self.metadata_card.update_text(
            "Comparação de metadados será implementada na próxima etapa."
        )

        self.findings_card.update_text(
            "Comparação de vestígios será implementada na próxima etapa."
        )

    def calculate_score(self, result: ComparisonResult) -> int:
        if not result.sections:
            return 0

        points = {
            "success": 100,
            "warning": 50,
            "critical": 0,
            "info": 50,
        }

        total = sum(points.get(section.status, 50) for section in result.sections)
        return int(total / len(result.sections))

    def _format_general(self, result: ComparisonResult) -> str:
        lines = [
            f"Arquivo A: {result.left_file}",
            f"Arquivo B: {result.right_file}",
            "",
            "Resumo técnico:",
            result.technical_summary,
            "",
            "Resultado por módulo:",
        ]

        for section in result.sections:
            icon = self._status_icon(section.status)
            lines.append(f"{icon} {section.title}")

        return "\n".join(lines)

    def _format_section(self, result: ComparisonResult, title: str) -> str:
        for section in result.sections:
            if section.title == title:
                icon = self._status_icon(section.status)
                return f"{icon} {section.title}\n\n{section.description}"

        return "Nenhuma informação disponível para esta seção."

    def _status_icon(self, status: str) -> str:
        return {
            "success": "✅",
            "warning": "⚠️",
            "critical": "❌",
            "info": "ℹ️",
        }.get(status, "ℹ️")

    def clear_comparison(self) -> None:
        self.left_result = None
        self.right_result = None
        self.comparison_result = None

        self.left_label.setText("Arquivo A: não selecionado")
        self.right_label.setText("Arquivo B: não selecionado")

        self.score_bar.setValue(0)
        self.score_label.setText("Score de compatibilidade: 0%")

        for index in range(self.tabs.count()):
            widget = self.tabs.widget(index)
            if hasattr(widget, "update_text"):
                widget.update_text("Nenhuma comparação realizada.")
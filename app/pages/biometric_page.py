from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from PySide6.QtCore import QEvent, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult
from app.models.biometric_report import (
    BiometricConstraintEvaluation,
    BiometricReport,
    ConstraintEvaluationStatus,
)
from app.widgets.base_card import BaseCard


class BiometricPage(QWidget):
    """Apresenta fatos já normalizados de um relatório biométrico."""

    DEMOGRAPHIC_NAMES = {
        "ESTIMATED_AGE",
        "FEMALE_CONFIDENCE",
        "MALE_CONFIDENCE",
    }
    COMPACT_BREAKPOINT = 820

    def __init__(self) -> None:
        super().__init__()
        self.report: BiometricReport | None = None
        self.header_cards: list[QFrame] = []
        self.metric_rows: list[tuple[QFrame, str, str, str]] = []
        self.restriction_rows: list[
            tuple[QFrame, ConstraintEvaluationStatus]
        ] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.stack = QStackedWidget()
        self.empty_label = QLabel(
            "Nenhum relatório biométrico reconhecido para o arquivo selecionado."
        )
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        self.stack.addWidget(self.empty_label)

        self.content = QWidget()
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(14, 14, 14, 14)
        self.content_layout.setSpacing(14)

        self.header_card = BaseCard("Relatório biométrico")
        self.header_grid = QGridLayout()
        self.header_grid.setSpacing(10)
        self.header_card.body_layout.addLayout(self.header_grid)

        self.decision_card = BaseCard("Decisão declarada")
        self.decision_layout = QVBoxLayout()
        self.decision_card.body_layout.addLayout(self.decision_layout)

        self.technical_card = BaseCard("Informações técnicas")
        self.technical_layout = QVBoxLayout()
        self.technical_card.body_layout.addLayout(self.technical_layout)

        self.algorithms_card = BaseCard("Algoritmos")
        self.configured_algorithms_layout = QVBoxLayout()
        self.result_algorithms_layout = QVBoxLayout()
        self.algorithms_card.body_layout.addWidget(
            self._section_label("Algoritmos configurados")
        )
        self.algorithms_card.body_layout.addLayout(
            self.configured_algorithms_layout
        )
        self.algorithms_card.body_layout.addWidget(
            self._section_label("Resultados algorítmicos")
        )
        self.algorithms_card.body_layout.addLayout(
            self.result_algorithms_layout
        )

        self.metrics_card = BaseCard("Métricas")
        metric_filters = QHBoxLayout()
        self.metric_search = QLineEdit()
        self.metric_search.setPlaceholderText(
            "Filtrar por nome, categoria ou nome normalizado..."
        )
        self.metric_category = QComboBox()
        self.metric_category.addItem("Todas as categorias", "")
        metric_filters.addWidget(self.metric_search, 1)
        metric_filters.addWidget(self.metric_category)
        self.metrics_layout = QVBoxLayout()
        self.metrics_card.body_layout.addLayout(metric_filters)
        self.metrics_card.body_layout.addLayout(self.metrics_layout)
        self.metric_search.textChanged.connect(self._filter_metrics)
        self.metric_category.currentIndexChanged.connect(self._filter_metrics)

        self.restrictions_card = BaseCard("Restrições")
        self.show_all_constraints = QCheckBox("Mostrar todas as restrições")
        self.restrictions_layout = QVBoxLayout()
        self.restrictions_card.body_layout.addWidget(
            self.show_all_constraints
        )
        self.restrictions_card.body_layout.addLayout(
            self.restrictions_layout
        )
        self.show_all_constraints.toggled.connect(
            self._filter_restrictions
        )

        self.evidences_card = BaseCard("Evidências referenciadas")
        self.evidences_layout = QVBoxLayout()
        self.evidences_card.body_layout.addLayout(self.evidences_layout)

        self.limitations_card = BaseCard("Limitações técnicas")
        limitations = QLabel(
            "Algoritmos proprietários não foram reproduzidos.\n"
            "A decisão é preservada como declaração do fornecedor.\n"
            "Não houve validação biométrica independente.\n"
            "Evidências externas não foram analisadas quando não disponibilizadas."
        )
        limitations.setWordWrap(True)
        limitations.setObjectName("MutedText")
        self.limitations_card.body_layout.addWidget(limitations)

        findings_note = QLabel(
            "Vestígios biométricos relacionados foram encaminhados à área de Vestígios."
        )
        findings_note.setWordWrap(True)
        findings_note.setObjectName("MutedText")

        for widget in (
            self.header_card,
            self.decision_card,
            self.technical_card,
            self.algorithms_card,
            self.metrics_card,
            self.restrictions_card,
            self.evidences_card,
            self.limitations_card,
            findings_note,
        ):
            self.content_layout.addWidget(widget)
        self.content_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(self.content)
        self.stack.addWidget(scroll)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.stack)
        self.stack.setCurrentIndex(0)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.set_report(result.biometric_report)

    def set_report(self, report: BiometricReport | None) -> None:
        self.report = report
        if report is None:
            self.stack.setCurrentIndex(0)
            return
        self._render_header(report)
        self._render_decision(report)
        self._render_technical(report)
        self._render_algorithms(report)
        self._render_metrics(report)
        self._render_restrictions(report)
        self._render_evidences(report)
        self.stack.setCurrentIndex(1)

    def _render_header(self, report: BiometricReport) -> None:
        self._clear_layout(self.header_grid)
        self.header_cards.clear()
        metadata = report.metadata
        face = self._mapping(metadata.get("faceliveness_library"))
        video = self._mapping(metadata.get("video_library"))
        raw = self._mapping(report.raw_payload)
        values = (
            ("Fornecedor", report.provider),
            ("Produto", report.product),
            ("Versão", self._version(report.version, face.get("revision"))),
            ("Biblioteca de vídeo", self._library(video)),
            ("Workflow", report.workflow),
            ("Perfil", metadata.get("profile_name")),
            ("Servidor", raw.get("server")),
            ("Tarefa", raw.get("task")),
        )
        for label, value in values:
            self.header_cards.append(self._value_card(label, value))
        self._reflow_header()

    def _render_decision(self, report: BiometricReport) -> None:
        self._clear_layout(self.decision_layout)
        if not report.decisions:
            self.decision_layout.addWidget(QLabel("Não informado"))
            return
        decision = report.decisions[0]
        literal = QLabel(self._display(decision.value))
        literal.setObjectName("CardTitle")
        literal.setWordWrap(True)
        self.decision_layout.addWidget(literal)
        self.decision_layout.addWidget(QLabel("Resultado declarado pelo fornecedor"))
        self.decision_layout.addWidget(
            self._pair("Score", decision.metadata.get("score"))
        )
        self.decision_layout.addWidget(
            self._pair("Score FRR", decision.metadata.get("score_frr"))
        )
        feedback = decision.metadata.get("feedback")
        if feedback:
            self.decision_layout.addWidget(self._pair("Feedback", feedback))
        notice = QLabel(
            "Resultado declarado pelo fornecedor, não reproduzido independentemente pelo ForensiHash."
        )
        notice.setWordWrap(True)
        notice.setObjectName("MutedText")
        self.decision_layout.addWidget(notice)

    def _render_technical(self, report: BiometricReport) -> None:
        self._clear_layout(self.technical_layout)
        parameters = self._mapping(
            report.metadata.get("workflow_parameters")
        )
        capture = self._mapping(report.metadata.get("autocapture"))
        values = [
            ("Quantidade de imagens", report.metadata.get("images_count")),
            ("Frame capturado", capture.get("captured_frame_index")),
            (
                "Frame construído",
                self._boolean(capture.get("captured_frame_is_constructed")),
            ),
            ("Security level", parameters.get("security_level")),
            ("Qualidade JPEG", parameters.get("jpeg_quality_level")),
            ("Modo de detecção facial", parameters.get("face_detection_mode")),
        ]
        values.extend(
            (f"Timestamp — {name}", self._timestamp(value))
            for name, value in report.timestamps.items()
        )
        for label, value in values:
            self.technical_layout.addWidget(self._pair(label, value))

    def _render_algorithms(self, report: BiometricReport) -> None:
        self._clear_layout(self.configured_algorithms_layout)
        self._clear_layout(self.result_algorithms_layout)
        configured = [item for item in report.algorithms if item.category == "configured"]
        results = [item for item in report.algorithms if item.category == "result"]
        self._algorithm_rows(self.configured_algorithms_layout, configured, False)
        self._algorithm_rows(self.result_algorithms_layout, results, True)

    def _algorithm_rows(self, layout, algorithms, show_score: bool) -> None:
        if not algorithms:
            layout.addWidget(QLabel("Não informado"))
            return
        for algorithm in algorithms:
            fields = [f"Nome: {algorithm.original_name}"]
            if show_score:
                fields.append(f"Score: {self._display(algorithm.score)}")
            fields.append(f"Threshold: {self._display(algorithm.threshold)}")
            if algorithm.feedback:
                fields.append(f"Feedback: {self._display(algorithm.feedback)}")
            layout.addWidget(self._row(" · ".join(fields)))

    def _render_metrics(self, report: BiometricReport) -> None:
        self._clear_layout(self.metrics_layout)
        self.metric_rows.clear()
        self.metric_category.blockSignals(True)
        self.metric_category.clear()
        self.metric_category.addItem("Todas as categorias", "")
        categories: set[str] = set()
        states = {
            item.metric.source_path: self._status_label(item.status)
            for item in report.constraint_evaluations
        }
        for metric in report.metrics:
            if self._is_demographic(metric.category, metric.original_name):
                continue
            category = metric.category or "Não informado"
            categories.add(category)
            normalized = metric.canonical_name or "Não informado"
            state = states.get(metric.source_path, "Não avaliada")
            text = (
                f"{category} · {metric.original_name} · "
                f"Valor: {self._display(metric.value)} · "
                f"Normalizado: {normalized} · Estado: {state}"
            )
            row = self._row(text)
            self.metrics_layout.addWidget(row)
            self.metric_rows.append(
                (row, metric.original_name.casefold(), category.casefold(), normalized.casefold())
            )
        for category in sorted(categories):
            self.metric_category.addItem(category, category)
        self.metric_category.blockSignals(False)
        if not self.metric_rows:
            self.metrics_layout.addWidget(QLabel("Não informado"))
        self._filter_metrics()

    def _render_restrictions(self, report: BiometricReport) -> None:
        self._clear_layout(self.restrictions_layout)
        self.restriction_rows.clear()
        evaluated = {id(item.constraint) for item in report.constraint_evaluations}
        for evaluation in report.constraint_evaluations:
            if self._is_demographic(
                evaluation.metric.category,
                evaluation.metric.original_name,
            ):
                continue
            row = self._restriction_row(evaluation)
            self.restrictions_layout.addWidget(row)
            self.restriction_rows.append((row, evaluation.status))
        for constraint in report.constraints:
            if id(constraint) in evaluated:
                continue
            synthetic = BiometricConstraintEvaluation(
                metric=self._missing_metric(constraint),
                constraint=constraint,
                observed_value=None,
                unit=None,
                status=ConstraintEvaluationStatus.NOT_EVALUATED,
                justification="Métrica observada não disponibilizada.",
            )
            row = self._restriction_row(synthetic)
            self.restrictions_layout.addWidget(row)
            self.restriction_rows.append((row, synthetic.status))
        if not self.restriction_rows:
            self.restrictions_layout.addWidget(QLabel("Não informado"))
        self.show_all_constraints.setChecked(False)
        self._filter_restrictions()

    def _render_evidences(self, report: BiometricReport) -> None:
        self._clear_layout(self.evidences_layout)
        if not report.evidences:
            self.evidences_layout.addWidget(QLabel("Não informado"))
            return
        for evidence in report.evidences:
            frames = evidence.metadata.get("frames")
            timestamp = None
            if isinstance(frames, list) and frames and isinstance(frames[0], Mapping):
                timestamp = frames[0].get("timestamp")
            text = (
                f"Tipo: {self._display(evidence.evidence_type)}\n"
                f"Referência original: {self._display(evidence.original_reference)}\n"
                f"Quantidade: {self._display(evidence.metadata.get('count'))}\n"
                f"Timestamp: {self._display(timestamp)}\n"
                f"Disponibilidade: {self._availability(evidence.exists)}\n\n"
                "Referência registrada no ambiente de origem. O arquivo correspondente "
                "não foi disponibilizado localmente."
            )
            self.evidences_layout.addWidget(self._row(text))

    def _filter_metrics(self, *_args) -> None:
        query = self.metric_search.text().strip().casefold()
        category = str(self.metric_category.currentData() or "").casefold()
        for row, name, row_category, normalized in self.metric_rows:
            matches_text = not query or any(
                query in value for value in (name, row_category, normalized)
            )
            matches_category = not category or row_category == category
            row.setVisible(matches_text and matches_category)

    def _filter_restrictions(self, *_args) -> None:
        visible_by_default = {
            ConstraintEvaluationStatus.BELOW_MINIMUM,
            ConstraintEvaluationStatus.ABOVE_MAXIMUM,
            ConstraintEvaluationStatus.NOT_EVALUATED,
        }
        show_all = self.show_all_constraints.isChecked()
        for row, status in self.restriction_rows:
            row.setVisible(show_all or status in visible_by_default)

    def resizeEvent(self, event: QEvent) -> None:
        self._reflow_header(event.size().width())
        super().resizeEvent(event)

    def _reflow_header(self, width: int | None = None) -> None:
        if not self.header_cards:
            return
        width = self.width() if width is None else width
        columns = 1 if width < self.COMPACT_BREAKPOINT else 2
        for index, card in enumerate(self.header_cards):
            self.header_grid.removeWidget(card)
            self.header_grid.addWidget(card, index // columns, index % columns)

    @staticmethod
    def _value_card(label: str, value: Any) -> QFrame:
        card = QFrame()
        card.setObjectName("BaseCard")
        layout = QVBoxLayout(card)
        title = QLabel(label)
        title.setObjectName("MutedText")
        content = QLabel(BiometricPage._display(value))
        content.setWordWrap(True)
        content.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(title)
        layout.addWidget(content)
        return card

    @staticmethod
    def _pair(label: str, value: Any) -> QLabel:
        widget = QLabel(f"{label}: {BiometricPage._display(value)}")
        widget.setWordWrap(True)
        widget.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return widget

    @staticmethod
    def _row(text: str) -> QFrame:
        row = QFrame()
        row.setObjectName("BaseCard")
        layout = QVBoxLayout(row)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(label)
        return row

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("SectionTitle")
        return label

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @staticmethod
    def _mapping(value: Any) -> Mapping[str, Any]:
        return value if isinstance(value, Mapping) else {}

    @staticmethod
    def _display(value: Any) -> str:
        if value is None or value == "" or value == [] or value == {}:
            return "Não informado"
        if isinstance(value, bool):
            return "Sim" if value else "Não"
        if isinstance(value, list):
            return ", ".join(str(item) for item in value) or "Não informado"
        return str(value)

    @staticmethod
    def _version(version: Any, revision: Any) -> str:
        parts = [str(value) for value in (version, revision) if value]
        return " ".join(parts) or "Não informado"

    @staticmethod
    def _library(data: Mapping[str, Any]) -> str:
        product = data.get("product")
        version = BiometricPage._version(data.get("version"), data.get("revision"))
        if not product:
            return version
        return f"{product} — {version}"

    @staticmethod
    def _boolean(value: Any) -> str:
        if value is True:
            return "Sim"
        if value is False:
            return "Não"
        return "Não informado"

    @staticmethod
    def _timestamp(value: Any) -> str:
        return value.isoformat() if isinstance(value, datetime) else BiometricPage._display(value)

    @staticmethod
    def _availability(value: bool | None) -> str:
        if value is True:
            return "Disponível"
        if value is False:
            return "Não disponível"
        return "Não verificada"

    @classmethod
    def _is_demographic(cls, category: str | None, name: str) -> bool:
        upper = name.upper()
        return (
            (category or "").upper() == "DEMOGRAPHICS"
            or upper in cls.DEMOGRAPHIC_NAMES
            or upper.startswith("RACE_")
        )

    @staticmethod
    def _status_label(status: ConstraintEvaluationStatus) -> str:
        return {
            ConstraintEvaluationStatus.BELOW_MINIMUM: "Abaixo do mínimo",
            ConstraintEvaluationStatus.WITHIN_RANGE: "Dentro do intervalo",
            ConstraintEvaluationStatus.PREFERRED: "Preferencial",
            ConstraintEvaluationStatus.ABOVE_MAXIMUM: "Acima do máximo",
            ConstraintEvaluationStatus.NOT_EVALUATED: "Não avaliada",
        }[status]

    @classmethod
    def _restriction_row(cls, evaluation: BiometricConstraintEvaluation) -> QFrame:
        constraint = evaluation.constraint
        text = (
            f"Métrica: {evaluation.metric.original_name} · "
            f"Valor observado: {cls._display(evaluation.observed_value)} · "
            f"Mínimo: {cls._display(constraint.minimum)} · "
            f"Preferencial: {cls._display(constraint.preferred)} · "
            f"Máximo: {cls._display(constraint.maximum)} · "
            f"Estado: {cls._status_label(evaluation.status)}"
        )
        return cls._row(text)

    @staticmethod
    def _missing_metric(constraint):
        from app.models.biometric_report import BiometricMetric

        return BiometricMetric(
            original_name=constraint.original_name,
            canonical_name=constraint.canonical_name,
            value=None,
        )

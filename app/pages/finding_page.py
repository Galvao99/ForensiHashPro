from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.investigation.correlation_finding import CorrelationFinding
from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.widgets.finding_card import FindingCard


class FindingPage(QWidget):
    """
    Painel visual dos vestígios técnicos e das correlações investigativas.
    """

    FILTER_ALL = "all"
    FILTER_ALERTS = "alerts"
    FILTER_SUCCESS = "success"
    FILTER_INFO = "info"

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("FindingPage")

        self.findings: list[object] = []
        self.current_filter = self.FILTER_ALL
        self.card_widgets: list[FindingCard] = []
        self._columns = 2

        self._build_ui()

    def _build_ui(self) -> None:
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(4, 4, 4, 16)
        self.root_layout.setSpacing(16)

        self.root_layout.addWidget(self._build_header())
        self.root_layout.addWidget(self._build_filter_bar())

        self.empty_state = self._build_empty_state()
        self.root_layout.addWidget(self.empty_state)

        self.cards_container = QWidget()
        self.cards_container.setObjectName("FindingCardsContainer")

        self.cards_layout = QGridLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setHorizontalSpacing(14)
        self.cards_layout.setVerticalSpacing(14)
        self.cards_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self.root_layout.addWidget(self.cards_container)
        self.root_layout.addStretch()

        self.empty_state.setVisible(True)
        self.cards_container.setVisible(False)

    def _build_header(self) -> QWidget:
        container = QFrame()
        container.setObjectName("FindingPageHeader")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(12)

        title = QLabel("Vestígios Técnicos")
        title.setObjectName("FindingPageTitle")

        subtitle = QLabel(
            "Evidências isoladas e correlações entre os arquivos analisados."
        )
        subtitle.setObjectName("FindingPageSubtitle")
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        summary_layout = QHBoxLayout()
        summary_layout.setSpacing(9)

        self.total_summary = self._create_summary_label(
            "Total",
            "0",
            "neutral",
        )

        self.critical_summary = self._create_summary_label(
            "Críticos",
            "0",
            "critical",
        )

        self.warning_summary = self._create_summary_label(
            "Alertas",
            "0",
            "warning",
        )

        self.success_summary = self._create_summary_label(
            "Compatíveis",
            "0",
            "success",
        )

        self.info_summary = self._create_summary_label(
            "Informações",
            "0",
            "info",
        )

        for widget in (
            self.total_summary,
            self.critical_summary,
            self.warning_summary,
            self.success_summary,
            self.info_summary,
        ):
            summary_layout.addWidget(widget)

        summary_layout.addStretch()
        layout.addLayout(summary_layout)

        return container

    def _create_summary_label(
        self,
        label: str,
        value: str,
        summary_type: str,
    ) -> QLabel:
        widget = QLabel(f"{label}: {value}")
        widget.setObjectName("FindingSummaryBadge")
        widget.setProperty("summaryType", summary_type)
        widget.setAlignment(Qt.AlignCenter)
        widget.setMinimumHeight(29)

        return widget

    def _build_filter_bar(self) -> QWidget:
        container = QWidget()

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.filter_group = QButtonGroup(self)
        self.filter_group.setExclusive(True)

        filters = (
            ("Todos", self.FILTER_ALL),
            ("Alertas", self.FILTER_ALERTS),
            ("Compatíveis", self.FILTER_SUCCESS),
            ("Informações", self.FILTER_INFO),
        )

        for text, filter_value in filters:
            button = QPushButton(text)
            button.setObjectName("FindingFilterButton")
            button.setCheckable(True)

            if filter_value == self.FILTER_ALL:
                button.setChecked(True)

            button.clicked.connect(
                lambda checked,
                selected_filter=filter_value: (
                    self._set_filter(selected_filter)
                    if checked
                    else None
                )
            )

            self.filter_group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()

        return container

    def _build_empty_state(self) -> QWidget:
        container = QFrame()
        container.setObjectName("FindingEmptyState")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 42, 24, 42)
        layout.setSpacing(9)

        icon = QLabel("⌕")
        icon.setObjectName("FindingEmptyIcon")
        icon.setAlignment(Qt.AlignCenter)

        self.empty_title = QLabel("Nenhum vestígio disponível")
        self.empty_title.setObjectName("FindingEmptyTitle")
        self.empty_title.setAlignment(Qt.AlignCenter)

        self.empty_description = QLabel(
            "Analise um arquivo ou uma pasta para visualizar os resultados."
        )
        self.empty_description.setObjectName("FindingEmptyDescription")
        self.empty_description.setAlignment(Qt.AlignCenter)
        self.empty_description.setWordWrap(True)

        layout.addWidget(icon)
        layout.addWidget(self.empty_title)
        layout.addWidget(self.empty_description)

        return container

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        """
        Mostra os vestígios individuais do arquivo selecionado.

        As correlações entre vários arquivos são recebidas por
        update_correlation_result().
        """

        legacy_findings = getattr(
            result,
            "findings",
            None,
        )

        if isinstance(legacy_findings, list):
            self.findings = list(legacy_findings)
        else:
            self.findings = []

        self._update_summary()
        self._render_cards()

    def update_correlation_result(
        self,
        correlation_result: CorrelationResult,
    ) -> None:
        """
        Mostra os findings gerados pela Investigation Engine.
        """

        self.findings = list(
            correlation_result.findings
        )

        self._update_summary()
        self._render_cards()

    def update_combined_results(
        self,
        *,
        analysis_result: AnalysisResult | None,
        correlation_result: CorrelationResult | None,
    ) -> None:
        """
        Combina os findings antigos do arquivo com as correlações
        investigativas do conjunto analisado.
        """

        combined: list[object] = []

        if analysis_result is not None:
            legacy_findings = getattr(
                analysis_result,
                "findings",
                None,
            )

            if isinstance(legacy_findings, list):
                combined.extend(legacy_findings)

        if correlation_result is not None:
            combined.extend(
                correlation_result.findings
            )

        self.findings = combined

        self._update_summary()
        self._render_cards()

    def _update_summary(self) -> None:
        total = len(self.findings)

        critical = self._count_severity("critical")
        warning = self._count_severity("warning")
        success = self._count_severity("ok")
        info = self._count_severity("info")

        self.total_summary.setText(f"Total: {total}")
        self.critical_summary.setText(
            f"Críticos: {critical}"
        )
        self.warning_summary.setText(
            f"Alertas: {warning}"
        )
        self.success_summary.setText(
            f"Compatíveis: {success}"
        )
        self.info_summary.setText(
            f"Informações: {info}"
        )

    def _count_severity(
        self,
        severity: str,
    ) -> int:
        return sum(
            1
            for finding in self.findings
            if self._normalize_severity(finding) == severity
        )

    def _set_filter(
        self,
        filter_value: str,
    ) -> None:
        self.current_filter = filter_value
        self._render_cards()

    def _filtered_findings(self) -> list[object]:
        if self.current_filter == self.FILTER_ALL:
            return list(self.findings)

        if self.current_filter == self.FILTER_ALERTS:
            return [
                finding
                for finding in self.findings
                if self._normalize_severity(finding)
                in {
                    "warning",
                    "critical",
                }
            ]

        if self.current_filter == self.FILTER_SUCCESS:
            return [
                finding
                for finding in self.findings
                if self._normalize_severity(finding) == "ok"
            ]

        if self.current_filter == self.FILTER_INFO:
            return [
                finding
                for finding in self.findings
                if self._normalize_severity(finding) == "info"
            ]

        return list(self.findings)

    def _render_cards(self) -> None:
        self._clear_cards()

        findings = self._filtered_findings()

        if not findings:
            self.cards_container.setVisible(False)
            self.empty_state.setVisible(True)

            if self.findings:
                self.empty_title.setText(
                    "Nenhum vestígio neste filtro"
                )
                self.empty_description.setText(
                    "Selecione outro filtro para visualizar os demais resultados."
                )
            else:
                self.empty_title.setText(
                    "Nenhum vestígio disponível"
                )
                self.empty_description.setText(
                    "Analise um arquivo ou uma pasta para visualizar os resultados."
                )

            return

        self.empty_state.setVisible(False)
        self.cards_container.setVisible(True)

        ordered_findings = sorted(
            findings,
            key=self._finding_sort_key,
        )

        for index, finding in enumerate(
            ordered_findings
        ):
            card = FindingCard(finding)

            row = index // self._columns
            column = index % self._columns

            self.cards_layout.addWidget(
                card,
                row,
                column,
                alignment=Qt.AlignTop,
            )

            self.card_widgets.append(card)

        for column in range(self._columns):
            self.cards_layout.setColumnStretch(
                column,
                1,
            )

    def _finding_sort_key(
        self,
        finding: object,
    ) -> tuple[int, str]:
        severity_order = {
            "critical": 0,
            "warning": 1,
            "ok": 2,
            "info": 3,
        }

        severity = self._normalize_severity(
            finding
        )

        title = str(
            getattr(
                finding,
                "title",
                "Vestígio técnico",
            )
        )

        return (
            severity_order.get(severity, 99),
            title.lower(),
        )

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        self.card_widgets.clear()

    def resizeEvent(self, event) -> None:
        new_columns = self._calculate_columns(
            event.size().width()
        )

        if new_columns != self._columns:
            self._columns = new_columns
            self._render_cards()

        super().resizeEvent(event)

    def _calculate_columns(
        self,
        width: int,
    ) -> int:
        if width >= 1500:
            return 3

        if width >= 830:
            return 2

        return 1

    @staticmethod
    def _normalize_severity(
        finding: object,
    ) -> str:
        severity = getattr(
            finding,
            "severity",
            "info",
        )

        value = getattr(
            severity,
            "value",
            severity,
        )

        normalized = str(value).strip().lower()

        aliases = {
            "success": "ok",
            "error": "critical",
            "danger": "critical",
            "warn": "warning",
        }

        return aliases.get(
            normalized,
            normalized or "info",
        )
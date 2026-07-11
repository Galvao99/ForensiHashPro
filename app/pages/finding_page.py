from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.widgets.file_investigation_panel import (
    FileInvestigationPanel,
)
from app.widgets.finding_card import FindingCard


class FindingPage(QWidget):
    """
    Painel investigativo do arquivo atualmente selecionado.
    """

    FILTER_ALL = "all"
    FILTER_ALERTS = "alerts"
    FILTER_SUCCESS = "success"
    FILTER_INFO = "info"

    CATEGORY_ORDER = (
        "ocr",
        "metadata",
        "signature",
        "network",
        "correlation",
        "integrity",
        "other",
    )

    CATEGORY_TITLES = {
        "ocr": "Conteúdo extraído e OCR",
        "metadata": "Metadados e softwares",
        "signature": "Assinatura digital",
        "network": "Rede e endereços IP",
        "correlation": "Correlações entre arquivos",
        "integrity": "Integridade e estrutura",
        "other": "Outras informações técnicas",
    }

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("FindingPage")

        self.current_result: AnalysisResult | None = None
        self.correlation_result: CorrelationResult | None = None

        self.findings: list[object] = []
        self.current_filter = self.FILTER_ALL

        self._build_ui()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(4, 4, 4, 10)
        root.setSpacing(14)

        root.addWidget(
            self._build_header()
        )

        root.addWidget(
            self._build_filter_bar()
        )

        body = QHBoxLayout()
        body.setSpacing(16)

        self.left_scroll = QScrollArea()
        self.left_scroll.setObjectName(
            "FindingLeftScroll"
        )
        self.left_scroll.setWidgetResizable(True)
        self.left_scroll.setFrameShape(
            QFrame.NoFrame
        )
        self.left_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.left_content = QWidget()
        self.left_content.setObjectName(
            "FindingLeftContent"
        )

        self.left_layout = QVBoxLayout(
            self.left_content
        )
        self.left_layout.setContentsMargins(
            0,
            0,
            4,
            0,
        )
        self.left_layout.setSpacing(14)
        self.left_layout.setAlignment(
            Qt.AlignTop
        )

        self.left_scroll.setWidget(
            self.left_content
        )

        self.file_panel = FileInvestigationPanel()

        body.addWidget(
            self.left_scroll,
            stretch=1,
        )
        body.addWidget(
            self.file_panel,
            stretch=0,
        )

        root.addLayout(
            body,
            stretch=1,
        )

    def _build_header(self) -> QWidget:
        container = QFrame()
        container.setObjectName(
            "FindingPageHeader"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            18,
            16,
            18,
            16,
        )
        layout.setSpacing(12)

        title = QLabel(
            "Vestígios Técnicos"
        )
        title.setObjectName(
            "FindingPageTitle"
        )

        subtitle = QLabel(
            "Informações extraídas, evidências técnicas e "
            "correlações relacionadas ao arquivo selecionado."
        )
        subtitle.setObjectName(
            "FindingPageSubtitle"
        )
        subtitle.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(subtitle)

        summary = QHBoxLayout()
        summary.setSpacing(8)

        self.total_summary = self._summary_badge(
            "Total",
            "neutral",
        )
        self.critical_summary = self._summary_badge(
            "Críticos",
            "critical",
        )
        self.warning_summary = self._summary_badge(
            "Alertas",
            "warning",
        )
        self.success_summary = self._summary_badge(
            "Compatíveis",
            "success",
        )
        self.info_summary = self._summary_badge(
            "Informações",
            "info",
        )

        for widget in (
            self.total_summary,
            self.critical_summary,
            self.warning_summary,
            self.success_summary,
            self.info_summary,
        ):
            summary.addWidget(widget)

        summary.addStretch()
        layout.addLayout(summary)

        return container

    def _summary_badge(
        self,
        text: str,
        badge_type: str,
    ) -> QLabel:
        label = QLabel(f"{text}: 0")
        label.setObjectName(
            "FindingSummaryBadge"
        )
        label.setProperty(
            "summaryType",
            badge_type,
        )
        label.setAlignment(Qt.AlignCenter)

        return label

    def _build_filter_bar(self) -> QWidget:
        container = QWidget()

        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        group = QButtonGroup(self)
        group.setExclusive(True)

        filters = (
            ("Todos", self.FILTER_ALL),
            ("Alertas", self.FILTER_ALERTS),
            ("Compatíveis", self.FILTER_SUCCESS),
            ("Informações", self.FILTER_INFO),
        )

        for text, value in filters:
            button = QPushButton(text)
            button.setObjectName(
                "FindingFilterButton"
            )
            button.setCheckable(True)

            if value == self.FILTER_ALL:
                button.setChecked(True)

            button.clicked.connect(
                lambda checked,
                filter_value=value: (
                    self._set_filter(filter_value)
                    if checked
                    else None
                )
            )

            group.addButton(button)
            layout.addWidget(button)

        layout.addStretch()

        return container

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        self.current_result = result
        self.file_panel.update_analysis(result)

        self._collect_findings()
        self._render()

    def update_correlation_result(
        self,
        correlation_result: CorrelationResult,
    ) -> None:
        self.correlation_result = correlation_result

        self._collect_findings()
        self._render()

    def update_combined_results(
        self,
        *,
        analysis_result: AnalysisResult | None,
        correlation_result: CorrelationResult | None,
    ) -> None:
        self.current_result = analysis_result
        self.correlation_result = correlation_result

        if analysis_result is not None:
            self.file_panel.update_analysis(
                analysis_result
            )
        else:
            self.file_panel.clear()

        self._collect_findings()
        self._render()

    def _collect_findings(self) -> None:
        findings: list[object] = []

        if self.current_result is not None:
            findings.extend(
                self.current_result.findings
            )

        if self.correlation_result is not None:
            current_file = self._current_file_name()

            for finding in self.correlation_result.findings:
                if self._belongs_to_current_file(
                    finding,
                    current_file,
                ):
                    findings.append(finding)

        self.findings = findings
        self._update_summary()

    def _belongs_to_current_file(
        self,
        finding: object,
        current_file: str,
    ) -> bool:
        source_file = str(
            getattr(
                finding,
                "source_file",
                "",
            )
            or ""
        )

        target_file = str(
            getattr(
                finding,
                "target_file",
                "",
            )
            or ""
        )

        if not source_file and not target_file:
            return True

        return current_file in {
            source_file,
            target_file,
        }

    def _render(self) -> None:
        self._clear_left_layout()

        filtered = self._filtered_findings()

        if not filtered:
            self.left_layout.addWidget(
                self._empty_state()
            )
            self.left_layout.addStretch()
            return

        categories: dict[str, list[object]] = {}

        for finding in filtered:
            category = self._finding_category(
                finding
            )

            categories.setdefault(
                category,
                [],
            ).append(finding)

        for category in self.CATEGORY_ORDER:
            category_findings = categories.get(
                category,
                [],
            )

            if not category_findings:
                continue

            self.left_layout.addWidget(
                self._build_category_section(
                    category,
                    category_findings,
                )
            )

        self.left_layout.addStretch()

    def _build_category_section(
        self,
        category: str,
        findings: list[object],
    ) -> QWidget:
        section = QFrame()
        section.setObjectName(
            "InvestigationSection"
        )

        layout = QVBoxLayout(section)
        layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        layout.setSpacing(10)

        header = QHBoxLayout()

        title = QLabel(
            self.CATEGORY_TITLES.get(
                category,
                "Informações técnicas",
            )
        )
        title.setObjectName(
            "InvestigationSectionTitle"
        )

        count = QLabel(
            str(len(findings))
        )
        count.setObjectName(
            "InvestigationSectionCount"
        )
        count.setAlignment(Qt.AlignCenter)
        count.setFixedSize(27, 23)

        header.addWidget(title)
        header.addWidget(count)
        header.addStretch()

        layout.addLayout(header)

        ordered = sorted(
            findings,
            key=self._finding_sort_key,
        )

        for finding in ordered:
            layout.addWidget(
                FindingCard(finding)
            )

        return section

    def _finding_category(
        self,
        finding: object,
    ) -> str:
        rule_id = str(
            getattr(
                finding,
                "rule_id",
                "",
            )
        ).lower()

        title = str(
            getattr(
                finding,
                "title",
                "",
            )
        ).lower()

        category = str(
            getattr(
                finding,
                "category",
                "",
            )
        ).lower()

        searchable = " ".join(
            (
                rule_id,
                title,
                category,
            )
        )

        if any(
            value in searchable
            for value in (
                "ocr",
                "cpf",
                "cnpj",
                "telefone",
                "email",
                "e-mail",
                "conteúdo textual",
                "data contratual",
                "datas localizadas",
            )
        ):
            return "ocr"

        if any(
            value in searchable
            for value in (
                "producer",
                "creator",
                "metadata",
                "metadado",
                "create_date",
                "modifydate",
                "pactuação",
            )
        ):
            return "metadata"

        if any(
            value in searchable
            for value in (
                "signature",
                "assinatura",
                "certificado",
                "signatário",
            )
        ):
            return "signature"

        if any(
            value in searchable
            for value in (
                "ip",
                "network",
                "rede",
                "proxy",
                "vpn",
                "tor",
                "geolocalização",
            )
        ):
            return "network"

        if any(
            value in searchable
            for value in (
                "hash_match",
                "hash_unmatched",
                "correlation",
                "correspondente",
                "correlação",
                "arquivos distintos",
            )
        ):
            return "correlation"

        if any(
            value in searchable
            for value in (
                "integrity",
                "integridade",
                "magic",
                "estrutura",
            )
        ):
            return "integrity"

        return "other"

    def _filtered_findings(
        self,
    ) -> list[object]:
        if self.current_filter == self.FILTER_ALL:
            return list(self.findings)

        if self.current_filter == self.FILTER_ALERTS:
            return [
                finding
                for finding in self.findings
                if self._severity(finding)
                in {
                    "warning",
                    "critical",
                }
            ]

        if self.current_filter == self.FILTER_SUCCESS:
            return [
                finding
                for finding in self.findings
                if self._severity(finding) == "ok"
            ]

        if self.current_filter == self.FILTER_INFO:
            return [
                finding
                for finding in self.findings
                if self._severity(finding) == "info"
            ]

        return list(self.findings)

    def _set_filter(
        self,
        filter_value: str,
    ) -> None:
        self.current_filter = filter_value
        self._render()

    def _update_summary(self) -> None:
        total = len(self.findings)

        critical = self._count("critical")
        warning = self._count("warning")
        success = self._count("ok")
        info = self._count("info")

        self.total_summary.setText(
            f"Total: {total}"
        )
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

    def _count(
        self,
        severity: str,
    ) -> int:
        return sum(
            1
            for finding in self.findings
            if self._severity(finding)
            == severity
        )

    def _finding_sort_key(
        self,
        finding: object,
    ) -> tuple[int, str]:
        order = {
            "critical": 0,
            "warning": 1,
            "ok": 2,
            "info": 3,
        }

        return (
            order.get(
                self._severity(finding),
                99,
            ),
            str(
                getattr(
                    finding,
                    "title",
                    "",
                )
            ).lower(),
        )

    def _severity(
        self,
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
            "warn": "warning",
            "error": "critical",
            "danger": "critical",
        }

        return aliases.get(
            normalized,
            normalized or "info",
        )

    def _current_file_name(self) -> str:
        if self.current_result is None:
            return ""

        return self.current_result.file_info.name

    def _empty_state(self) -> QWidget:
        container = QFrame()
        container.setObjectName(
            "FindingEmptyState"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            20,
            45,
            20,
            45,
        )
        layout.setSpacing(8)

        title = QLabel(
            "Nenhuma informação neste filtro"
        )
        title.setObjectName(
            "FindingEmptyTitle"
        )
        title.setAlignment(Qt.AlignCenter)

        description = QLabel(
            "Selecione outro filtro ou analise um arquivo "
            "com informações técnicas disponíveis."
        )
        description.setObjectName(
            "FindingEmptyDescription"
        )
        description.setAlignment(
            Qt.AlignCenter
        )
        description.setWordWrap(True)

        layout.addWidget(title)
        layout.addWidget(description)

        return container

    def _clear_left_layout(self) -> None:
        while self.left_layout.count():
            item = self.left_layout.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()
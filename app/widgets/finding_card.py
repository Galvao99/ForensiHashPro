import json
from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.investigation.correlation_finding import CorrelationFinding
from app.widgets.badge_widget import BadgeWidget


class FindingCard(QFrame):
    """
    Card visual que representa um único vestígio técnico.
    """

    details_toggled = Signal(bool)

    SEVERITY_LABELS = {
        "ok": "Compatível",
        "info": "Informação",
        "warning": "Atenção",
        "critical": "Crítico",
    }

    SEVERITY_ICONS = {
        "ok": "✓",
        "info": "ℹ",
        "warning": "⚠",
        "critical": "✕",
    }

    def __init__(
        self,
        finding: CorrelationFinding,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.finding = finding
        self.details_visible = False
        self.severity = self._normalize_severity(
            getattr(finding, "severity", "info")
        )

        self.setObjectName("InvestigationFindingCard")
        self.setProperty("severity", self.severity)

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.setMinimumWidth(310)
        self.setMaximumWidth(650)

        self._build_ui()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 16, 18, 16)
        root_layout.setSpacing(12)

        root_layout.addLayout(self._build_header())

        description = QLabel(self._get_description())
        description.setObjectName("FindingDescription")
        description.setWordWrap(True)
        description.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        root_layout.addWidget(description)

        badges_widget = self._build_badges()

        if badges_widget is not None:
            root_layout.addWidget(badges_widget)

        relation_widget = self._build_file_relation()

        if relation_widget is not None:
            root_layout.addWidget(relation_widget)

        if self._get_metadata():
            root_layout.addWidget(
                self._build_details_section()
            )

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        icon_label = QLabel(
            self.SEVERITY_ICONS.get(
                self.severity,
                "•",
            )
        )
        icon_label.setObjectName("FindingSeverityIcon")
        icon_label.setProperty(
            "severity",
            self.severity,
        )
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setFixedSize(32, 32)

        title_layout = QVBoxLayout()
        title_layout.setContentsMargins(0, 0, 0, 0)
        title_layout.setSpacing(2)

        title = QLabel(
            str(
                getattr(
                    self.finding,
                    "title",
                    "Vestígio técnico",
                )
            )
        )
        title.setObjectName("FindingTitle")
        title.setWordWrap(True)

        severity_label = QLabel(
            self.SEVERITY_LABELS.get(
                self.severity,
                self.severity.replace(
                    "_",
                    " ",
                ).capitalize(),
            )
        )
        severity_label.setObjectName(
            "FindingSeverityLabel"
        )
        severity_label.setProperty(
            "severity",
            self.severity,
        )

        title_layout.addWidget(title)
        title_layout.addWidget(severity_label)

        layout.addWidget(
            icon_label,
            alignment=Qt.AlignTop,
        )
        layout.addLayout(title_layout, stretch=1)

        return layout

    def _build_badges(self) -> QWidget | None:
        badges = getattr(
            self.finding,
            "badges",
            [],
        )

        if not badges:
            return None

        container = QWidget()
        container.setObjectName(
            "FindingBadgesContainer"
        )

        layout = QGridLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setHorizontalSpacing(7)
        layout.setVerticalSpacing(7)

        columns = 3

        for index, badge in enumerate(badges):
            row = index // columns
            column = index % columns

            layout.addWidget(
                BadgeWidget(badge),
                row,
                column,
                alignment=Qt.AlignLeft,
            )

        layout.setColumnStretch(columns, 1)

        return container

    def _build_file_relation(self) -> QWidget | None:
        source_file = getattr(
            self.finding,
            "source_file",
            None,
        )

        target_file = getattr(
            self.finding,
            "target_file",
            None,
        )

        legacy_files = getattr(
            self.finding,
            "related_files",
            [],
        )

        if not source_file and legacy_files:
            source_file = legacy_files[0]

        if not target_file and len(legacy_files) > 1:
            target_file = legacy_files[1]

        if not source_file and not target_file:
            return None

        container = QFrame()
        container.setObjectName("FindingRelationBox")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(5)

        if source_file:
            source_label = QLabel(
                f"Arquivo: {source_file}"
            )
            source_label.setObjectName(
                "FindingSourceFile"
            )
            source_label.setWordWrap(True)
            source_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )

            layout.addWidget(source_label)

        if target_file:
            target_label = QLabel(
                f"Relacionado a: {target_file}"
            )
            target_label.setObjectName(
                "FindingTargetFile"
            )
            target_label.setWordWrap(True)
            target_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )

            layout.addWidget(target_label)

        return container

    def _build_details_section(self) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.details_button = QPushButton(
            "Exibir detalhes técnicos"
        )
        self.details_button.setObjectName(
            "FindingDetailsButton"
        )
        self.details_button.setCheckable(True)
        self.details_button.clicked.connect(
            self._toggle_details
        )

        self.details_label = QLabel(
            self._format_metadata(
                self._get_metadata()
            )
        )
        self.details_label.setObjectName(
            "FindingMetadata"
        )
        self.details_label.setWordWrap(True)
        self.details_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self.details_label.setVisible(False)

        layout.addWidget(
            self.details_button,
            alignment=Qt.AlignLeft,
        )
        layout.addWidget(self.details_label)

        return container

    def _toggle_details(
        self,
        checked: bool,
    ) -> None:
        self.details_visible = checked
        self.details_label.setVisible(checked)

        self.details_button.setText(
            "Ocultar detalhes técnicos"
            if checked
            else "Exibir detalhes técnicos"
        )

        self.details_toggled.emit(checked)

    def _get_description(self) -> str:
        description = getattr(
            self.finding,
            "description",
            "",
        )

        if description:
            return str(description)

        return str(
            getattr(
                self.finding,
                "message",
                "",
            )
        )

    def _get_metadata(self) -> dict[str, Any]:
        metadata = getattr(
            self.finding,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            return metadata

        evidence = getattr(
            self.finding,
            "evidence",
            None,
        )

        if isinstance(evidence, dict):
            return evidence

        return {}

    def _format_metadata(
        self,
        metadata: dict[str, Any],
    ) -> str:
        try:
            return json.dumps(
                metadata,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        except (TypeError, ValueError):
            return str(metadata)

    @staticmethod
    def _normalize_severity(
        severity: object,
    ) -> str:
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
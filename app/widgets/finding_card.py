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

from app.widgets.badge_widget import BadgeWidget


class FindingCard(QFrame):
    """
    Card visual de uma informação ou correlação técnica.
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
        finding: object,
        parent=None,
    ) -> None:
        super().__init__(parent)

        self.finding = finding

        self.severity = self._normalize_severity(
            getattr(
                finding,
                "severity",
                "info",
            )
        )

        self.setObjectName(
            "InvestigationFindingCard"
        )
        self.setProperty(
            "severity",
            self.severity,
        )

        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            16,
            14,
            16,
            14,
        )
        layout.setSpacing(10)

        layout.addLayout(
            self._build_header()
        )

        description = self._get_description()

        if description:
            description_label = QLabel(
                description
            )
            description_label.setObjectName(
                "FindingDescription"
            )
            description_label.setWordWrap(True)
            description_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )

            layout.addWidget(
                description_label
            )

        badges = self._build_badges()

        if badges is not None:
            layout.addWidget(badges)

        relation = self._build_file_relation()

        if relation is not None:
            layout.addWidget(relation)

        metadata = self._get_metadata()

        if metadata:
            layout.addWidget(
                self._build_details_section(
                    metadata
                )
            )

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(10)

        icon = QLabel(
            self.SEVERITY_ICONS.get(
                self.severity,
                "•",
            )
        )
        icon.setObjectName(
            "FindingSeverityIcon"
        )
        icon.setProperty(
            "severity",
            self.severity,
        )
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignCenter)

        texts = QVBoxLayout()
        texts.setContentsMargins(0, 0, 0, 0)
        texts.setSpacing(2)

        title = QLabel(
            str(
                getattr(
                    self.finding,
                    "title",
                    "Informação técnica",
                )
            )
        )
        title.setObjectName("FindingTitle")
        title.setWordWrap(True)

        severity = QLabel(
            self.SEVERITY_LABELS.get(
                self.severity,
                "Informação",
            )
        )
        severity.setObjectName(
            "FindingSeverityLabel"
        )
        severity.setProperty(
            "severity",
            self.severity,
        )

        texts.addWidget(title)
        texts.addWidget(severity)

        layout.addWidget(
            icon,
            alignment=Qt.AlignTop,
        )
        layout.addLayout(texts, stretch=1)

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

        grid = QGridLayout(container)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(7)
        grid.setVerticalSpacing(7)

        columns = 4

        for index, badge in enumerate(badges):
            row = index // columns
            column = index % columns

            grid.addWidget(
                BadgeWidget(badge),
                row,
                column,
                alignment=Qt.AlignLeft,
            )

        grid.setColumnStretch(
            columns,
            1,
        )

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

        if not source_file and not target_file:
            return None

        container = QFrame()
        container.setObjectName(
            "FindingRelationBox"
        )

        layout = QHBoxLayout(container)
        layout.setContentsMargins(
            10,
            7,
            10,
            7,
        )
        layout.setSpacing(8)

        if source_file:
            source = QLabel(
                str(source_file)
            )
            source.setObjectName(
                "FindingSourceFile"
            )
            source.setWordWrap(True)

            layout.addWidget(source)

        if source_file and target_file:
            arrow = QLabel("→")
            arrow.setObjectName(
                "FindingRelationArrow"
            )
            layout.addWidget(arrow)

        if target_file:
            target = QLabel(
                str(target_file)
            )
            target.setObjectName(
                "FindingTargetFile"
            )
            target.setWordWrap(True)

            layout.addWidget(target)

        layout.addStretch()

        return container

    def _build_details_section(
        self,
        metadata: dict[str, Any],
    ) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        button = QPushButton(
            "Exibir detalhes técnicos"
        )
        button.setObjectName(
            "FindingDetailsButton"
        )
        button.setCheckable(True)

        details = QLabel(
            self._format_metadata(metadata)
        )
        details.setObjectName(
            "FindingMetadata"
        )
        details.setWordWrap(True)
        details.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        details.setVisible(False)

        def toggle_details(
            checked: bool,
        ) -> None:
            details.setVisible(checked)

            button.setText(
                "Ocultar detalhes técnicos"
                if checked
                else "Exibir detalhes técnicos"
            )

            self.details_toggled.emit(
                checked
            )

        button.clicked.connect(
            toggle_details
        )

        layout.addWidget(
            button,
            alignment=Qt.AlignLeft,
        )
        layout.addWidget(details)

        return container

    def _get_description(self) -> str:
        description = getattr(
            self.finding,
            "description",
            "",
        )

        return str(description or "")

    def _get_metadata(self) -> dict[str, Any]:
        metadata = getattr(
            self.finding,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            return metadata

        return {}

    @staticmethod
    def _format_metadata(
        metadata: dict[str, Any],
    ) -> str:
        return json.dumps(
            metadata,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

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
            "warn": "warning",
            "error": "critical",
            "danger": "critical",
        }

        return aliases.get(
            normalized,
            normalized or "info",
        )
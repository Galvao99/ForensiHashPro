from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from typing import Any

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QBoxLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.widgets.badge_widget import BadgeWidget
from app.widgets.flow_layout import FlowLayout


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
        "info": "i",
        "warning": "!",
        "critical": "×",
    }

    def __init__(
        self,
        finding: object,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.finding = finding
        self.severity = self._normalize_severity(
            getattr(finding, "severity", "info")
        )

        self.setObjectName("InvestigationFindingCard")
        self.setProperty("severity", self.severity)
        self.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self._relation_layout: QBoxLayout | None = None
        self._relation_arrow: QLabel | None = None
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(11)

        layout.addLayout(self._build_header())

        description = self._get_description()
        if description:
            description_label = QLabel(description)
            description_label.setObjectName("FindingDescription")
            description_label.setWordWrap(True)
            description_label.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )
            description_label.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Minimum,
            )
            layout.addWidget(description_label)

        badges = self._build_badges()
        if badges is not None:
            layout.addWidget(badges)

        relation = self._build_file_relation()
        if relation is not None:
            layout.addWidget(relation)

        metadata = self._get_metadata()
        if metadata:
            layout.addWidget(
                self._build_details_section(metadata)
            )

    def _build_header(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(11)

        icon = QLabel(
            self.SEVERITY_ICONS.get(self.severity, "•")
        )
        icon.setObjectName("FindingSeverityIcon")
        icon.setProperty("severity", self.severity)
        icon.setFixedSize(32, 32)
        icon.setAlignment(Qt.AlignCenter)

        texts_container = QWidget()
        texts_container.setObjectName(
            "FindingTransparentContainer"
        )

        texts = QVBoxLayout(texts_container)
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
        title.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        severity = QLabel(
            self.SEVERITY_LABELS.get(
                self.severity,
                "Informação",
            )
        )
        severity.setObjectName("FindingSeverityLabel")
        severity.setProperty("severity", self.severity)

        texts.addWidget(title)
        texts.addWidget(severity)

        layout.addWidget(icon, alignment=Qt.AlignTop)
        layout.addWidget(texts_container, stretch=1)

        return layout

    def _build_badges(self) -> QWidget | None:
        badges = getattr(self.finding, "badges", [])

        if not badges:
            return None

        container = QWidget()
        container.setObjectName(
            "FindingTransparentContainer"
        )

        flow = FlowLayout(container)

        for index, badge in enumerate(badges):
            widget = BadgeWidget(badge)
            widget.setSizePolicy(
                QSizePolicy.Maximum,
                QSizePolicy.Fixed,
            )

            flow.addWidget(widget)

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
        container.setObjectName("FindingRelationBox")
        container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        layout = QBoxLayout(QBoxLayout.LeftToRight, container)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(8)
        self._relation_layout = layout

        if source_file:
            source = QLabel(str(source_file))
            source.setObjectName("FindingSourceFile")
            source.setWordWrap(True)
            source.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )
            source.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Minimum,
            )
            layout.addWidget(source, stretch=1)

        if source_file and target_file:
            arrow = QLabel("→")
            arrow.setObjectName("FindingRelationArrow")
            arrow.setAlignment(Qt.AlignCenter)
            layout.addWidget(arrow)
            self._relation_arrow = arrow

        if target_file:
            target = QLabel(str(target_file))
            target.setObjectName("FindingTargetFile")
            target.setWordWrap(True)
            target.setTextInteractionFlags(
                Qt.TextSelectableByMouse
            )
            target.setSizePolicy(
                QSizePolicy.Expanding,
                QSizePolicy.Minimum,
            )
            layout.addWidget(target, stretch=1)

        return container

    def resizeEvent(self, event: QEvent) -> None:
        if self._relation_layout is not None:
            compact = event.size().width() < 520
            self._relation_layout.setDirection(
                QBoxLayout.TopToBottom if compact else QBoxLayout.LeftToRight
            )
            if self._relation_arrow is not None:
                self._relation_arrow.setText("↓" if compact else "→")
        super().resizeEvent(event)

    def _build_details_section(
        self,
        metadata: dict[str, Any],
    ) -> QWidget:
        container = QWidget()
        container.setObjectName(
            "FindingTransparentContainer"
        )

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)

        button = QPushButton(
            "Exibir detalhes técnicos"
        )
        button.setObjectName("FindingDetailsButton")
        button.setCheckable(True)
        button.setCursor(Qt.PointingHandCursor)
        button.setFocusPolicy(Qt.NoFocus)

        details = QLabel(
            self._format_metadata(metadata)
        )
        details.setObjectName("FindingMetadata")
        details.setWordWrap(True)
        details.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        details.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )
        details.setVisible(False)

        def toggle_details(checked: bool) -> None:
            details.setVisible(checked)
            button.setText(
                "Ocultar detalhes técnicos"
                if checked
                else "Exibir detalhes técnicos"
            )
            self.details_toggled.emit(checked)

        button.clicked.connect(toggle_details)

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
            details = dict(metadata)
            for field_name in ("finding_id", "category", "source_engine", "confidence", "evidence", "entities", "limitations"):
                value = getattr(self.finding, field_name, None)
                if value in (None, "", [], ()):
                    continue
                if isinstance(value, (list, tuple)):
                    details[field_name] = [asdict(item) if is_dataclass(item) else item for item in value]
                else:
                    details[field_name] = value
            return details

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

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.correlation.v2.identity import source_file_identity
from app.correlation.v2.pipeline import CanonicalCasePipelineResult
from app.models.timeline_event import TimelineEvent
from app.presentation.timeline import TimelinePresentation
from app.ui.theme import LIGHT_THEME, ThemeTokens
from app.widgets.timeline_v2 import DetailedTimeline, VisualTimeline


class TimelinePage(QWidget):
    """Two presentation-only views over one selected artifact dataset."""

    source_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelinePage")
        self.presentation = TimelinePresentation((), (), (), ())
        self.selected_event_id: str | None = None
        self._events: tuple[TimelineEvent, ...] = ()
        self._artifact_id: str | None = None
        self._case_id: str | None = None
        self._canonical_result: CanonicalCasePipelineResult | None = None
        self._tokens = LIGHT_THEME

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(12)
        heading = QVBoxLayout()
        heading.setSpacing(2)
        title = QLabel("Timeline")
        title.setObjectName("TimelinePageTitle")
        subtitle = QLabel(
            "Reconstrução cronológica das observações temporais da evidência digital."
        )
        subtitle.setObjectName("TimelinePageSubtitle")
        subtitle.setWordWrap(True)
        subtitle.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred,
        )
        self.artifact_context = QLabel("Nenhum artefato selecionado")
        self.artifact_context.setObjectName("TimelineArtifactContext")
        self.artifact_context.setWordWrap(True)
        self.artifact_context.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred,
        )
        heading.addWidget(title)
        heading.addWidget(subtitle)
        heading.addWidget(self.artifact_context)
        header.addLayout(heading, stretch=1)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        mode_control = QFrame()
        mode_control.setObjectName("TimelineModeControl")
        mode_layout = QHBoxLayout(mode_control)
        mode_layout.setContentsMargins(2, 2, 2, 2)
        mode_layout.setSpacing(0)
        self.detailed_button = self._mode_button("Detalhada", 0)
        self.visual_button = self._mode_button("Visual", 1)
        mode_layout.addWidget(self.detailed_button)
        mode_layout.addWidget(self.visual_button)
        header.addWidget(mode_control, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(header)

        self.views = QStackedWidget()
        self.views.setObjectName("TimelineViewStack")
        self.detailed = DetailedTimeline()
        self.visual = VisualTimeline()
        self.views.addWidget(self.detailed)
        self.views.addWidget(self.visual)
        root.addWidget(self.views, stretch=1)

        self.detailed.event_selected.connect(self._select_event)
        self.detailed.source_requested.connect(self.source_requested)
        self.visual.event_selected.connect(self._select_event)
        self.detailed_button.setChecked(True)
        self.views.setCurrentWidget(self.detailed)
        self.apply_theme(self._tokens)

    def _mode_button(self, label: str, index: int) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("TimelineModeButton")
        button.setCheckable(True)
        button.setAutoExclusive(True)
        button.setAccessibleName(f"Exibir Timeline {label.lower()}")
        button.setAccessibleDescription(
            "Altera somente a apresentação do conjunto temporal atual."
        )
        button.setMinimumWidth(76)
        button.setMinimumHeight(28)
        button.setMaximumHeight(28)
        button.setStyleSheet("text-align: center;")
        button.clicked.connect(
            lambda checked=False, target=index: checked and self._set_view(target)
        )
        self.mode_group.addButton(button, index)
        return button

    def apply_theme(self, tokens: ThemeTokens) -> None:
        self._tokens = tokens
        self.visual.apply_theme(tokens)

    def update_analysis(self, analysis_result) -> None:
        events = tuple(getattr(analysis_result, "timeline_events", ()) or ())
        canonical = tuple(
            event for event in events if isinstance(event, TimelineEvent)
        )
        artifact_id = self._artifact_identity(analysis_result)
        artifact_changed = artifact_id != self._artifact_id
        self._artifact_id = artifact_id
        self._events = canonical
        if artifact_changed:
            self.selected_event_id = None
        file_info = getattr(analysis_result, "file_info", None)
        filename = getattr(
            file_info, "name", canonical[0].filename if canonical else "Artefato",
        )
        self.artifact_context.setText(
            f"{filename} · {len(canonical)} observação(ões) canônica(s)"
        )
        self.artifact_context.setToolTip(str(getattr(file_info, "path", "")))
        self._rebuild_presentation()

    def update_result(self, analysis_result) -> None:
        self.update_analysis(analysis_result)

    def update_case_result(
        self,
        case_id: str | None,
        canonical_result: CanonicalCasePipelineResult | None,
    ) -> None:
        if case_id != self._case_id:
            self._case_id = case_id
            self._canonical_result = None
            self.selected_event_id = None
        if canonical_result is not None:
            result_case_id = getattr(canonical_result.case_result, "case_id", None)
            if not case_id or result_case_id != case_id:
                return
        self._canonical_result = canonical_result
        self._rebuild_presentation()

    def show_event_details(self, event_id: str) -> None:
        """Select an existing event without changing views or deriving data."""
        self._select_event(event_id)

    def _set_view(self, index: int) -> None:
        self.views.setCurrentIndex(index)
        if self.selected_event_id:
            self.detailed.select_event(self.selected_event_id)
            self.visual.set_selected_event(self.selected_event_id)

    def _select_event(self, event_id: str) -> None:
        if event_id not in {event.event_id for event in self._events}:
            return
        self.selected_event_id = event_id
        self.visual.set_selected_event(event_id)
        self.detailed.select_event(event_id)

    def _rebuild_presentation(self) -> None:
        self.presentation = TimelinePresentation.from_events(
            self._events,
            canonical_result=self._canonical_result,
            artifact_id=self._artifact_id,
        )
        self.detailed.set_presentation(self.presentation)
        self.visual.set_presentation(self.presentation)
        valid_ids = {event.event_id for event in self._events}
        if self.selected_event_id not in valid_ids:
            self.selected_event_id = None
        self.detailed.select_event(self.selected_event_id)
        self.visual.set_selected_event(self.selected_event_id)

    @staticmethod
    def _artifact_identity(analysis_result) -> str | None:
        file_info = getattr(analysis_result, "file_info", None)
        if file_info is None:
            return None
        hashes = getattr(analysis_result, "hashes", None)
        evidence_source = getattr(analysis_result, "evidence_source", None)
        return source_file_identity(
            display_name=file_info.name,
            path=file_info.path,
            sha256=getattr(hashes, "sha256", None),
            session_id=(
                getattr(evidence_source, "evidence_id", None)
                if evidence_source is not None else None
            ),
        ).stable_id

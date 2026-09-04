from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QVBoxLayout,
    QWidget,
)

from app.models.timeline_event import TimelineEvent
from app.presentation.timeline import TimelinePresentation
from app.widgets.timeline_v2 import DetailedTimeline, VisualTimeline


class TimelinePage(QWidget):
    """Two presentation-only views over the selected result's canonical events."""

    source_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelinePage")
        self.presentation = TimelinePresentation((), (), (), ())
        self.selected_event_id: str | None = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 18)
        root.setSpacing(12)
        header = QHBoxLayout()
        heading = QVBoxLayout()
        title = QLabel("Timeline")
        title.setObjectName("TimelinePageTitle")
        subtitle = QLabel("Informações temporais observadas e sua proveniência técnica.")
        subtitle.setObjectName("TimelinePageSubtitle")
        heading.addWidget(title)
        heading.addWidget(subtitle)
        header.addLayout(heading, stretch=1)

        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.detailed_button = self._mode_button("Detalhada", 0)
        self.visual_button = self._mode_button("Visual", 1)
        header.addWidget(self.detailed_button)
        header.addWidget(self.visual_button)
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
        self.visual.details_requested.connect(self.show_event_details)
        self.detailed_button.setChecked(True)

    def _mode_button(self, label: str, index: int) -> QPushButton:
        button = QPushButton(label)
        button.setObjectName("TimelineModeButton")
        button.setCheckable(True)
        button.setAccessibleName(f"Exibir Timeline {label.lower()}")
        button.clicked.connect(
            lambda checked=False, target=index: checked and self.views.setCurrentIndex(target)
        )
        self.mode_group.addButton(button)
        return button

    def update_analysis(self, analysis_result) -> None:
        events = tuple(getattr(analysis_result, "timeline_events", ()) or ())
        canonical = tuple(event for event in events if isinstance(event, TimelineEvent))
        self.presentation = TimelinePresentation.from_events(canonical)
        self.detailed.set_presentation(self.presentation)
        self.visual.set_presentation(self.presentation)
        if self.selected_event_id not in {event.event_id for event in canonical}:
            self.selected_event_id = None
            self.visual.set_selected_event(None)

    def update_result(self, analysis_result) -> None:
        self.update_analysis(analysis_result)

    def show_event_details(self, event_id: str) -> None:
        self._select_event(event_id)
        self.detailed_button.setChecked(True)
        self.views.setCurrentWidget(self.detailed)
        self.detailed.select_event(event_id)

    def _select_event(self, event_id: str) -> None:
        self.selected_event_id = event_id
        self.visual.set_selected_event(event_id)

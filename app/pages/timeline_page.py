from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.services.timeline_service import TimelineService
from app.widgets.technical_timeline import TechnicalTimeline
from app.widgets.timeline_list import TimelineList


class TimelinePage(QWidget):
    """Página de timeline."""

    def __init__(self) -> None:
        super().__init__()

        self.timeline_list = TimelineList()
        self.timeline_service = TimelineService()
        self.technical_timeline = TechnicalTimeline()

        layout = QVBoxLayout()
        layout.addWidget(self.timeline_list)
        layout.addWidget(self.technical_timeline)

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.timeline_list.update_timeline(result)

        events, result_text = self.timeline_service.build_timeline(result)

        self.technical_timeline.update_timeline(events, result_text)
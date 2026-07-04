from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.services.timeline_service import TimelineService
from app.widgets.smart_timeline import SmartTimeline
from app.widgets.technical_timeline import TechnicalTimeline


class TimelinePage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("TimelinePage")

        self.timeline_service = TimelineService()
        self.current_result = None
        self.current_events = []
        self.current_result_text = ""

        self.title = QLabel("Linha Temporal Técnica")
        self.title.setObjectName("SectionTitle")

        self.subtitle = QLabel(
            "Comparação entre metadados, conteúdo contratual, assinatura digital, "
            "sistema de arquivos e abertura do arquivo."
        )
        self.subtitle.setObjectName("SectionSubtitle")
        self.subtitle.setWordWrap(True)

        self.smart_timeline = SmartTimeline()
        self.technical_timeline = TechnicalTimeline()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(18)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.smart_timeline)
        layout.addWidget(self.technical_timeline)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.current_result = result

        events, result_text = self.timeline_service.build_timeline(result)

        self.current_events = events
        self.current_result_text = result_text

        result.timeline_events = events
        result.timeline_result_text = result_text

        self.render_timeline()

    def render_timeline(self) -> None:
        self.smart_timeline.set_events(self.current_events)
        self.technical_timeline.update_timeline(
            self.current_events,
            self.current_result_text,
        )
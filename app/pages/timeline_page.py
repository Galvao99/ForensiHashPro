from PySide6.QtWidgets import QVBoxLayout, QWidget

from app.models import AnalysisResult
from app.widgets.timeline_list import TimelineList


class TimelinePage(QWidget):
    """Página de timeline."""

    def __init__(self) -> None:
        super().__init__()

        self.timeline_list = TimelineList()

        layout = QVBoxLayout()
        layout.addWidget(self.timeline_list)

        self.setLayout(layout)

    def update_analysis(self, result: AnalysisResult) -> None:
        self.timeline_list.update_timeline(result)
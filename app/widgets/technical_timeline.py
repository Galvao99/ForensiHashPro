from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.models.timeline_event import TimelineEvent


class TimelinePoint(QWidget):
    def __init__(self, event: TimelineEvent, show_line: bool = True) -> None:
        super().__init__()

        self.setObjectName("TimelinePoint")

        main_layout = QVBoxLayout(self)
        main_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        main_layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setAlignment(Qt.AlignCenter)
        top_layout.setSpacing(0)

        dot = QLabel("●")
        dot.setObjectName("TimelineDot")
        dot.setStyleSheet(f"color: {event.color}; font-size: 30px;")
        dot.setAlignment(Qt.AlignCenter)

        top_layout.addWidget(dot)

        if show_line:
            line = QFrame()
            line.setObjectName("TimelineConnector")
            line.setFixedHeight(2)
            line.setFixedWidth(110)
            top_layout.addWidget(line)

        title = QLabel(event.title)
        title.setObjectName("TimelineTitle")
        title.setAlignment(Qt.AlignCenter)

        date = QLabel(event.formatted_date())
        date.setObjectName("TimelineDate")
        date.setAlignment(Qt.AlignCenter)

        source = QLabel(event.source)
        source.setObjectName("TimelineSource")
        source.setAlignment(Qt.AlignCenter)

        description = QLabel(event.description)
        description.setObjectName("TimelineDescription")
        description.setWordWrap(True)
        description.setAlignment(Qt.AlignCenter)
        description.setFixedWidth(180)

        main_layout.addLayout(top_layout)
        main_layout.addWidget(title)
        main_layout.addWidget(date)
        main_layout.addWidget(source)
        main_layout.addWidget(description)


class TechnicalTimeline(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("TechnicalTimeline")

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)

        title = QLabel("Linha Temporal Técnica")
        title.setObjectName("SectionTitle")

        subtitle = QLabel(
            "Comparação entre metadados, conteúdo contratual, assinatura digital, sistema de arquivos e abertura do arquivo."
        )
        subtitle.setObjectName("SectionSubtitle")
        subtitle.setWordWrap(True)

        self.scroll = QScrollArea()
        self.scroll.setObjectName("TimelineScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.timeline_container = QWidget()
        self.timeline_layout = QHBoxLayout(self.timeline_container)
        self.timeline_layout.setAlignment(Qt.AlignLeft)
        self.timeline_layout.setSpacing(0)

        self.scroll.setWidget(self.timeline_container)

        self.result = QLabel("Nenhuma linha temporal gerada.")
        self.result.setObjectName("TimelineResult")
        self.result.setWordWrap(True)

        main_layout.addWidget(title)
        main_layout.addWidget(subtitle)
        main_layout.addWidget(self.scroll)
        main_layout.addWidget(self.result)

    def update_timeline(
        self,
        events: list[TimelineEvent],
        result_text: str,
    ) -> None:
        self._clear_layout()

        if not events:
            self.result.setText("Nenhum evento temporal foi identificado.")
            return

        for index, event in enumerate(events):
            show_line = index < len(events) - 1
            self.timeline_layout.addWidget(TimelinePoint(event, show_line))

        self.result.setText(result_text)

    def _clear_layout(self) -> None:
        while self.timeline_layout.count():
            item = self.timeline_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()
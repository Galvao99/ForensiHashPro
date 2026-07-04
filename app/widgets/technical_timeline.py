from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class TimelineEventCard(QFrame):
    def __init__(self, event) -> None:
        super().__init__()

        self.setObjectName("TimelineEventCard")

        dot = QLabel("●")
        dot.setObjectName("TimelineCardDot")
        dot.setStyleSheet(f"color: {getattr(event, 'color', '#60A5FA')};")
        dot.setAlignment(Qt.AlignCenter)

        title = QLabel(event.title)
        title.setObjectName("TimelineCardTitle")
        title.setAlignment(Qt.AlignCenter)
        title.setWordWrap(True)

        date = QLabel(event.formatted_date())
        date.setObjectName("TimelineCardDate")
        date.setAlignment(Qt.AlignCenter)

        source = QLabel(event.source)
        source.setObjectName("TimelineCardSource")
        source.setAlignment(Qt.AlignCenter)
        source.setWordWrap(True)

        description = QLabel(event.description)
        description.setObjectName("TimelineCardDescription")
        description.setAlignment(Qt.AlignCenter)
        description.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        layout.addWidget(dot)
        layout.addWidget(title)
        layout.addWidget(date)
        layout.addWidget(source)
        layout.addWidget(description)
        layout.addStretch()


class TechnicalTimeline(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("TechnicalTimeline")

        self.title = QLabel("Eventos da Linha Temporal")
        self.title.setObjectName("SectionTitle")

        self.subtitle = QLabel(
            "Eventos técnicos identificados no documento analisado."
        )
        self.subtitle.setObjectName("SectionSubtitle")
        self.subtitle.setWordWrap(True)

        self.cards_container = QWidget()
        self.cards_layout = QHBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(14)

        self.result_label = QLabel()
        self.result_label.setObjectName("TimelineResult")
        self.result_label.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(16)

        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)
        layout.addWidget(self.cards_container)
        layout.addWidget(self.result_label)

    def update_timeline(self, events, result_text: str) -> None:
        self._clear_cards()

        if not events:
            self.result_label.setText("Nenhum evento temporal identificado.")
            return

        events = sorted(events, key=lambda event: event.date)

        for event in events:
            card = TimelineEventCard(event)
            self.cards_layout.addWidget(card, stretch=1)

        self.result_label.setText(result_text)

    def _clear_cards(self) -> None:
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()
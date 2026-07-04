from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class TimelineNode(QWidget):
    clicked = Signal(object)

    def __init__(self, group: dict) -> None:
        super().__init__()

        self.group = group
        self.events = group["events"]
        self.first_event = self.events[0]

        self.setObjectName("TimelineNode")
        self.setCursor(Qt.PointingHandCursor)

        dot_text = "●"
        if len(self.events) > 1:
            dot_text = f"● {len(self.events)}"

        self.dot = QLabel(dot_text)
        self.dot.setObjectName("TimelineNodeDot")
        self.dot.setAlignment(Qt.AlignCenter)
        self.dot.setStyleSheet(f"color: {group['color']};")

        self.line = QFrame()
        self.line.setObjectName("TimelineNodeLine")
        self.line.setFixedHeight(34)

        title_text = (
            f"{len(self.events)} eventos"
            if len(self.events) > 1
            else self.first_event.title
        )

        self.title = QLabel(title_text)
        self.title.setObjectName("TimelineNodeTitle")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setWordWrap(True)

        self.date = QLabel(self.first_event.date.strftime("%d/%m/%Y"))
        self.date.setObjectName("TimelineNodeDate")
        self.date.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 0, 6, 0)
        layout.setSpacing(5)

        layout.addWidget(self.dot)
        layout.addWidget(self.line, alignment=Qt.AlignCenter)
        layout.addWidget(self.title)
        layout.addWidget(self.date)

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self.group)
        super().mousePressEvent(event)


class SmartTimeline(QWidget):
    group_selected = Signal(object)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("SmartTimeline")
        self.groups = []

        self.track = QFrame()
        self.track.setObjectName("SmartTimelineTrack")
        self.track.setFixedHeight(2)

        self.nodes_container = QWidget()
        self.nodes_layout = QHBoxLayout(self.nodes_container)
        self.nodes_layout.setContentsMargins(0, 0, 0, 0)
        self.nodes_layout.setSpacing(0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 18, 8, 18)
        layout.setSpacing(0)

        layout.addWidget(self.track)
        layout.addWidget(self.nodes_container)

    def set_events(self, events) -> None:
        valid_events = [
            event for event in events
            if getattr(event, "date", None)
        ]

        valid_events.sort(key=lambda event: event.date)
        self.groups = self._group_close_events(valid_events)
        self._render()

    def _render(self) -> None:
        self._clear_layout()

        if not self.groups:
            return

        for group in self.groups:
            node = TimelineNode(group)
            node.clicked.connect(self.group_selected.emit)
            self.nodes_layout.addWidget(node, stretch=1)

    def _group_close_events(self, events) -> list[dict]:
        groups = []

        for event in events:
            added = False

            for group in groups:
                delta = abs((event.date - group["date"]).total_seconds())

                # Agrupa eventos com até 10 minutos de diferença.
                if delta <= 600:
                    group["events"].append(event)
                    group["date"] = min(item.date for item in group["events"])
                    added = True
                    break

            if not added:
                groups.append(
                    {
                        "date": event.date,
                        "events": [event],
                        "color": getattr(event, "color", "#60A5FA"),
                    }
                )

        groups.sort(key=lambda group: group["date"])
        return groups

    def _clear_layout(self) -> None:
        while self.nodes_layout.count():
            item = self.nodes_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()
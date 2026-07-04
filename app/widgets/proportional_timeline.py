from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class ProportionalTimelineCard(QFrame):
    def __init__(self, group) -> None:
        super().__init__()

        self.setObjectName("ProportionalTimelineCard")

        events = group["events"]
        first = events[0]
        is_group = len(events) > 1

        dot = QLabel("●")
        dot.setObjectName("ProportionalTimelineDot")
        dot.setStyleSheet(f"color: {group['color']};")

        title_text = (
            f"{len(events)} eventos próximos"
            if is_group
            else first.title
        )

        title = QLabel(title_text)
        title.setObjectName("ProportionalTimelineTitle")
        title.setWordWrap(True)

        date = QLabel(first.formatted_date())
        date.setObjectName("ProportionalTimelineDate")

        if is_group:
            detail_text = "\n".join(event.title for event in events)
        else:
            detail_text = first.source

        detail = QLabel(detail_text)
        detail.setObjectName("ProportionalTimelineDetail")
        detail.setWordWrap(True)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(8)
        header.addWidget(dot)
        header.addWidget(title, stretch=1)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(date)
        layout.addWidget(detail)
        layout.addStretch()


class ProportionalTimeline(QWidget):
    def __init__(self):
        super().__init__()

        self.groups = []
        self.setObjectName("ProportionalTimeline")

        self.line = QLabel("Linha cronológica proporcional")
        self.line.setObjectName("ProportionalTimelineHeader")
        self.line.setAlignment(Qt.AlignCenter)

        self.grid = QGridLayout()
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(12)
        layout.addWidget(self.line)
        layout.addLayout(self.grid)

    def set_events(self, events):
        valid_events = [
            event for event in events
            if getattr(event, "date", None)
        ]

        valid_events.sort(key=lambda event: event.date)
        self.groups = self._group_close_events(valid_events)
        self._render_cards()

    def _render_cards(self):
        self._clear_grid()

        if not self.groups:
            return

        columns = self._columns_for_width()

        for index, group in enumerate(self.groups):
            row = index // columns
            column = index % columns

            card = ProportionalTimelineCard(group)
            self.grid.addWidget(card, row, column)

        for column in range(columns):
            self.grid.setColumnStretch(column, 1)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._render_cards()

    def _columns_for_width(self) -> int:
        width = self.width()

        if width < 700:
            return 1

        if width < 1050:
            return 2

        if width < 1400:
            return 3

        return min(5, max(1, len(self.groups)))

    def _group_close_events(self, events):
        groups = []

        for event in events:
            added = False

            for group in groups:
                delta = abs((event.date - group["date"]).total_seconds())

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

    def _clear_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()
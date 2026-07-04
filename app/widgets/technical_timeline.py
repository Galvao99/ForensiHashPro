from __future__ import annotations

from collections import Counter
from datetime import datetime

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class TechnicalTimeline(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TechnicalTimeline")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(10)

        self.filters = QHBoxLayout()
        self.filters.setSpacing(8)

        self.buttons = {}

        for label in ["Todos", "Criação", "Modificação", "Acesso", "Assinatura", "Sistema"]:
            button = QPushButton(label)
            button.setObjectName("TimelineFilterButton")
            button.setCheckable(True)
            button.clicked.connect(lambda _, value=label: self._apply_filter(value))
            self.buttons[label] = button
            self.filters.addWidget(button)

        self.filters.addStretch()

        self.scroll = QScrollArea()
        self.scroll.setObjectName("TimelineScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.container = QWidget()
        self.container.setObjectName("TimelineListContainer")

        self.list_layout = QVBoxLayout(self.container)
        self.list_layout.setContentsMargins(0, 0, 0, 0)
        self.list_layout.setSpacing(0)

        self.scroll.setWidget(self.container)

        self.footer = QLabel("")
        self.footer.setObjectName("TimelineFooter")

        root.addLayout(self.filters)
        root.addWidget(self.scroll, stretch=1)
        root.addWidget(self.footer)

        self.all_events = []
        self.active_filter = "Todos"
        self.buttons["Todos"].setChecked(True)

    def update_events(self, events: list[dict]) -> None:
        self.all_events = events or []
        self._update_filter_labels()
        self._render()

    def _apply_filter(self, value: str) -> None:
        self.active_filter = value

        for label, button in self.buttons.items():
            button.setChecked(label == value)

        self._render()

    def _render(self) -> None:
        self._clear()

        events = self._filtered_events()

        if not events:
            empty = QLabel("Nenhum evento técnico encontrado.")
            empty.setObjectName("TimelineEmpty")
            empty.setAlignment(Qt.AlignCenter)
            self.list_layout.addWidget(empty)
            self.footer.setText("Exibindo 0 eventos")
            return

        for index, event in enumerate(events):
            self.list_layout.addWidget(
                TimelineEventRow(
                    event=event,
                    is_first=index == 0,
                    is_last=index == len(events) - 1,
                )
            )

        self.list_layout.addStretch()
        self.footer.setText(f"Exibindo {len(events)} de {len(self.all_events)} eventos")

    def _filtered_events(self) -> list[dict]:
        if self.active_filter == "Todos":
            return self.all_events

        return [
            event
            for event in self.all_events
            if str(event.get("category", "")).lower() == self.active_filter.lower()
        ]

    def _update_filter_labels(self) -> None:
        counter = Counter(event.get("category", "Sistema") for event in self.all_events)

        for label, button in self.buttons.items():
            if label == "Todos":
                button.setText(f"Todos ({len(self.all_events)})")
            else:
                button.setText(f"{label} ({counter.get(label, 0)})")

    def _clear(self) -> None:
        while self.list_layout.count():
            item = self.list_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()


class TimelineEventRow(QFrame):
    def __init__(self, event: dict, is_first: bool, is_last: bool) -> None:
        super().__init__()
        self.setObjectName("TimelineEventRow")

        event_type = str(event.get("event_type", "info")).lower()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        time_box = QWidget()
        time_box.setObjectName("TimelineTimeBox")

        time_layout = QVBoxLayout(time_box)
        time_layout.setContentsMargins(0, 16, 0, 0)
        time_layout.setSpacing(6)

        date_label = QLabel(self._format_date(event.get("timestamp")))
        date_label.setObjectName("TimelineDateLabel")

        hour_badge = QLabel(self._format_hour(event.get("timestamp")))
        hour_badge.setObjectName("TimelineHourBadge")
        hour_badge.setAlignment(Qt.AlignCenter)

        time_layout.addWidget(date_label)
        time_layout.addWidget(hour_badge)
        time_layout.addStretch()

        marker = TimelineMarker(event_type, is_first, is_last)

        card = QFrame()
        card.setObjectName("TimelineEventCard")
        card.setProperty("eventType", event_type)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 3, 10, 3) # Card padding adjusted to 3 for top and bottom
        card_layout.setSpacing(3)

        top_line = QHBoxLayout()
        top_line.setSpacing(10)

        icon = QLabel(self._icon_for(event_type))
        icon.setObjectName("TimelineEventIcon")
        icon.setAlignment(Qt.AlignCenter)

        title = QLabel(event.get("title", "Evento técnico"))
        title.setObjectName("TimelineEventTitle")

        badge = QLabel(event.get("category", "Sistema"))
        badge.setObjectName("TimelineBadge")
        badge.setProperty("eventType", event_type)
        badge.setAlignment(Qt.AlignCenter)

        top_line.addWidget(icon)
        top_line.addWidget(title, stretch=1)
        top_line.addWidget(badge)

        description = QLabel(event.get("description", ""))
        description.setObjectName("TimelineEventDescription")
        description.setWordWrap(True)

        details = QLabel(event.get("details", ""))
        details.setObjectName("TimelineEventDetails")
        details.setWordWrap(True)

        source = QLabel(f"Fonte: {event.get('source', 'ForensiHash')}")
        source.setObjectName("TimelineSource")
        source.setAlignment(Qt.AlignRight)

        card_layout.addLayout(top_line)

        if event.get("description"):
            card_layout.addWidget(description)

        if event.get("details"):
            card_layout.addWidget(details)

        card_layout.addWidget(source)

        layout.addWidget(time_box)
        layout.addWidget(marker)
        layout.addWidget(card, stretch=1)

    def _icon_for(self, event_type: str) -> str:
        if event_type == "creation":
            return "📄"
        if event_type == "modification":
            return "✎"
        if event_type == "signature":
            return "🔗"
        if event_type == "access":
            return "👁"
        if event_type == "system":
            return "⚙"
        return "•"

    def _parse_date(self, value):
        if not value:
            return None

        text = str(value).replace("Z", "+00:00")

        for fmt in [
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ]:
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _format_date(self, value) -> str:
        parsed = self._parse_date(value)
        if not parsed:
            return "--/--/----"
        return parsed.strftime("%d/%m/%Y")

    def _format_hour(self, value) -> str:
        parsed = self._parse_date(value)
        if not parsed:
            return "--:--:--"
        return parsed.strftime("%H:%M:%S")


class TimelineMarker(QWidget):
    def __init__(self, event_type: str, is_first: bool, is_last: bool) -> None:
        super().__init__()
        self.setObjectName("TimelineMarker")
        self.setFixedWidth(34)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignHCenter)

        top_line = QFrame()
        top_line.setObjectName("TimelineVerticalLine")
        top_line.setFixedWidth(2)
        top_line.setVisible(not is_first)

        dot = QLabel("")
        dot.setObjectName("TimelineDot")
        dot.setProperty("eventType", event_type)
        dot.setAlignment(Qt.AlignCenter)
        dot.setFixedSize(18, 18)

        bottom_line = QFrame()
        bottom_line.setObjectName("TimelineVerticalLine")
        bottom_line.setFixedWidth(2)
        bottom_line.setVisible(not is_last)

        layout.addWidget(top_line, stretch=1, alignment=Qt.AlignHCenter)
        layout.addWidget(dot, alignment=Qt.AlignHCenter)
        layout.addWidget(bottom_line, stretch=1, alignment=Qt.AlignHCenter)


class TimelineSidePanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelineSidePanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.summary = TimelineSummaryCard()
        self.period = TimelineInfoCard("Período dos Eventos")
        self.quick = TimelineInfoCard("Visualização Rápida")

        layout.addWidget(self.summary)
        layout.addWidget(self.period)
        layout.addWidget(self.quick)
        layout.addStretch()

    def update_summary(self, events: list[dict]) -> None:
        counter = Counter(event.get("category", "Sistema") for event in events)

        self.summary.update_counts(
            total=len(events),
            creation=counter.get("Criação", 0),
            modification=counter.get("Modificação", 0),
            access=counter.get("Acesso", 0),
            signature=counter.get("Assinatura", 0),
            system=counter.get("Sistema", 0),
        )

        parsed_dates = [
            self._parse_date(event.get("timestamp"))
            for event in events
            if self._parse_date(event.get("timestamp"))
        ]

        if parsed_dates:
            first = min(parsed_dates)
            last = max(parsed_dates)

            self.period.set_lines(
                [
                    f"Primeiro evento:\n{first.strftime('%d/%m/%Y %H:%M:%S')}",
                    "",
                    f"Último evento:\n{last.strftime('%d/%m/%Y %H:%M:%S')}",
                ]
            )
        else:
            self.period.set_lines(["Sem datas identificadas."])

        quick_lines = [
            f"{self._format_date(event.get('timestamp'))} — {event.get('category', 'Evento')}"
            for event in events[:8]
        ]

        self.quick.set_lines(quick_lines or ["Sem eventos para exibir."])

    def _parse_date(self, value):
        if not value:
            return None

        text = str(value).replace("Z", "+00:00")

        for fmt in [
            "%Y:%m:%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ]:
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                pass

        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None

    def _format_date(self, value) -> str:
        parsed = self._parse_date(value)
        if not parsed:
            return "--/--/----"
        return parsed.strftime("%d/%m/%Y")


class TimelineSummaryCard(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("TimelineInfoCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        title = QLabel("Resumo da Timeline")
        title.setObjectName("TimelineInfoTitle")

        self.grid = QGridLayout()
        self.grid.setSpacing(10)

        self.cards = {
            "total": TimelineMiniStat("0", "Eventos"),
            "creation": TimelineMiniStat("0", "Criação"),
            "modification": TimelineMiniStat("0", "Modificação"),
            "access": TimelineMiniStat("0", "Acesso"),
            "signature": TimelineMiniStat("0", "Assinatura"),
            "system": TimelineMiniStat("0", "Sistema"),
        }

        self.grid.addWidget(self.cards["total"], 0, 0)
        self.grid.addWidget(self.cards["creation"], 0, 1)
        self.grid.addWidget(self.cards["modification"], 1, 0)
        self.grid.addWidget(self.cards["access"], 1, 1)
        self.grid.addWidget(self.cards["signature"], 2, 0)
        self.grid.addWidget(self.cards["system"], 2, 1)

        layout.addWidget(title)
        layout.addLayout(self.grid)

    def update_counts(
        self,
        total: int,
        creation: int,
        modification: int,
        access: int,
        signature: int,
        system: int,
    ) -> None:
        self.cards["total"].update_value(total)
        self.cards["creation"].update_value(creation)
        self.cards["modification"].update_value(modification)
        self.cards["access"].update_value(access)
        self.cards["signature"].update_value(signature)
        self.cards["system"].update_value(system)


class TimelineMiniStat(QFrame):
    def __init__(self, value: str, label: str) -> None:
        super().__init__()
        self.setObjectName("TimelineMiniStat")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        self.value = QLabel(str(value))
        self.value.setObjectName("TimelineMiniStatValue")
        self.value.setAlignment(Qt.AlignCenter)

        self.label = QLabel(label)
        self.label.setObjectName("TimelineMiniStatLabel")
        self.label.setAlignment(Qt.AlignCenter)

        layout.addWidget(self.value)
        layout.addWidget(self.label)

    def update_value(self, value: int) -> None:
        self.value.setText(str(value))


class TimelineInfoCard(QFrame):
    def __init__(self, title: str) -> None:
        super().__init__()
        self.setObjectName("TimelineInfoCard")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        self.title = QLabel(title)
        self.title.setObjectName("TimelineInfoTitle")

        self.content = QLabel("")
        self.content.setObjectName("TimelineInfoContent")
        self.content.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.content)

    def set_lines(self, lines: list[str]) -> None:
        self.content.setText("\n".join(lines))
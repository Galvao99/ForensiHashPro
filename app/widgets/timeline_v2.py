from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QPainter, QPalette, QPen
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from app.models.timeline_event import TimelineEvent
from app.presentation.timeline import TemporalScale, TimelinePoint, TimelinePresentation


_PRECISION_LABELS = {
    "year": "ano", "month": "mês", "day": "dia", "minute": "minuto",
    "second": "segundo", "millisecond": "milissegundo",
    "microsecond": "microssegundo", None: "não determinada",
}


def format_temporal(event: TimelineEvent) -> str:
    value = event.date
    if value is None:
        return event.raw_timestamp or "Data não determinada"
    formats = {
        "year": "%Y", "month": "%m/%Y", "day": "%d/%m/%Y",
        "minute": "%d/%m/%Y %H:%M", "second": "%d/%m/%Y %H:%M:%S",
        "millisecond": "%d/%m/%Y %H:%M:%S.%f",
        "microsecond": "%d/%m/%Y %H:%M:%S.%f",
    }
    text = value.strftime(formats.get(event.precision, "%d/%m/%Y %H:%M:%S"))
    if event.precision == "millisecond":
        text = text[:-3]
    if event.timezone_status == "explicit" and event.timezone:
        text += f" ({event.timezone})"
    elif event.timezone_status == "unknown":
        text += " (fuso não informado)"
    return text


class TimelineEventRow(QFrame):
    selected = Signal(str)
    source_requested = Signal(str)

    def __init__(self, event: TimelineEvent) -> None:
        super().__init__()
        self.timeline_event = event
        self.setObjectName("TimelineV2EventRow")
        self.setAccessibleName(f"{event.title}, {format_temporal(event)}")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)
        marker = QLabel("●")
        marker.setObjectName("TimelineV2Marker")
        marker.setAccessibleName("Evento temporal")
        layout.addWidget(marker, alignment=Qt.AlignmentFlag.AlignTop)
        content = QVBoxLayout()
        content.setSpacing(3)
        title = QLabel(event.title)
        title.setObjectName("TimelineV2EventTitle")
        observed = QLabel(format_temporal(event))
        observed.setObjectName("TimelineV2EventTime")
        provenance = QLabel(
            f"{event.source_type} · {event.source_engine} · {event.filename}"
        )
        provenance.setObjectName("TimelineV2Secondary")
        technical = QLabel(
            f"Valor observado: {event.raw_timestamp or 'não aplicável'} · "
            f"Precisão: {_PRECISION_LABELS.get(event.precision, event.precision)}"
        )
        technical.setObjectName("TimelineV2Secondary")
        technical.setWordWrap(True)
        content.addWidget(title)
        content.addWidget(observed)
        content.addWidget(provenance)
        content.addWidget(technical)
        if event.description:
            description = QLabel(event.description)
            description.setObjectName("TimelineV2Description")
            description.setWordWrap(True)
            content.addWidget(description)
        actions = QHBoxLayout()
        source = QPushButton("Ver fonte")
        source.setObjectName("TimelineSourceButton")
        source.setAccessibleName(f"Ver fonte de {event.title}")
        source.clicked.connect(lambda: self.source_requested.emit(event.event_id))
        actions.addWidget(source)
        actions.addStretch()
        content.addLayout(actions)
        layout.addLayout(content, stretch=1)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.timeline_event.event_id)
        super().mousePressEvent(event)


class DetailedTimeline(QWidget):
    event_selected = Signal(str)
    source_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.container = QWidget()
        self.items = QVBoxLayout(self.container)
        self.items.setContentsMargins(0, 0, 0, 0)
        self.items.setSpacing(6)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll)
        self._presentation: TimelinePresentation | None = None
        self._references_visible = False

    def set_presentation(self, presentation: TimelinePresentation) -> None:
        self._presentation = presentation
        self._render()

    def select_event(self, event_id: str) -> None:
        for index in range(self.items.count()):
            widget = self.items.itemAt(index).widget()
            if isinstance(widget, TimelineEventRow) and widget.timeline_event.event_id == event_id:
                widget.setFocus(Qt.FocusReason.OtherFocusReason)
                self.scroll.ensureWidgetVisible(widget)
                break

    def _render(self) -> None:
        while self.items.count():
            item = self.items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        presentation = self._presentation
        if presentation is None:
            return
        if not presentation.primary_points:
            empty = QLabel("Nenhum evento temporal primário disponível.")
            empty.setObjectName("TimelineV2Empty")
            self.items.addWidget(empty)
        for point in presentation.primary_points:
            row = TimelineEventRow(point.event)
            row.selected.connect(self.event_selected)
            row.source_requested.connect(self.source_requested)
            self.items.addWidget(row)
        references = QPushButton(
            f"Outras referências temporais ({len(presentation.other_references)}) · "
            f"{'Ocultar' if self._references_visible else 'Mostrar'}"
        )
        references.setObjectName("TimelineReferencesButton")
        references.setCheckable(True)
        references.setChecked(self._references_visible)
        references.clicked.connect(self._toggle_references)
        self.items.addWidget(references)
        if self._references_visible:
            for event in presentation.other_references[:100]:
                row = TimelineEventRow(event)
                row.selected.connect(self.event_selected)
                row.source_requested.connect(self.source_requested)
                self.items.addWidget(row)
            remaining = len(presentation.other_references) - 100
            if remaining > 0:
                self.items.addWidget(QLabel(f"{remaining} referência(s) adicionais não renderizadas nesta visão."))
        self.items.addStretch()

    def _toggle_references(self, checked: bool) -> None:
        self._references_visible = checked
        self._render()


@dataclass(frozen=True, slots=True)
class MarkerCluster:
    x: float
    points: tuple[TimelinePoint, ...]
    y: float = 0.0


def cluster_points(points: tuple[TimelinePoint, ...], scale: TemporalScale, width: float, threshold: float = 14.0) -> tuple[MarkerCluster, ...]:
    positioned = sorted(
        ((scale.position(point), point) for point in points),
        key=lambda item: (item[0] is None, item[0] or 0.0, item[1].event_id),
    )
    clusters: list[list[TimelinePoint]] = []
    positions: list[float] = []
    for normalized, point in positioned:
        if normalized is None:
            continue
        x = normalized * width
        if positions and abs(x - positions[-1]) <= threshold:
            clusters[-1].append(point)
            positions[-1] = sum((scale.position(item) or 0.0) * width for item in clusters[-1]) / len(clusters[-1])
        else:
            clusters.append([point])
            positions.append(x)
    return tuple(MarkerCluster(x, tuple(group)) for x, group in zip(positions, clusters))


class VisualTimeline(QWidget):
    event_selected = Signal(str)
    details_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("VisualTimeline")
        self.setAccessibleName("Timeline visual proporcional")
        self.setMinimumHeight(410)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.presentation = TimelinePresentation((), (), (), ())
        self.selected_event_id: str | None = None
        self.clusters: tuple[MarkerCluster, ...] = ()

    def set_presentation(self, presentation: TimelinePresentation) -> None:
        self.presentation = presentation
        self.update()

    def set_selected_event(self, event_id: str | None) -> None:
        self.selected_event_id = event_id
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        text = palette.color(QPalette.ColorRole.Text)
        muted = palette.color(QPalette.ColorRole.PlaceholderText)
        accent = palette.color(QPalette.ColorRole.Highlight)
        left, right = 44.0, max(45.0, self.width() - 44.0)
        width = right - left
        points = self.presentation.primary_points
        by_domain = {domain: tuple(point for point in points if point.domain == domain) for domain in ("instant", "civil")}
        available = [domain for domain in ("instant", "civil") if by_domain[domain]]
        if not available:
            painter.setPen(text)
            painter.drawText(QRectF(left, 100, width, 40), Qt.AlignmentFlag.AlignCenter, "Sem eventos temporalmente comparáveis")
            return
        painted: list[MarkerCluster] = []
        for lane, domain in enumerate(available):
            y = 145.0 + lane * 125.0
            scale_points = list(by_domain[domain])
            scale_points.extend(
                point for interval in self.presentation.intervals
                for point in (interval.start, interval.end) if point.domain == domain
            )
            scale = TemporalScale.for_points(scale_points)
            if scale is None:
                continue
            painter.setPen(QPen(muted, 2))
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            painter.drawText(QRectF(left, y - 112, width, 18), "Instantes com fuso" if domain == "instant" else "Tempo civil · fuso não informado")
            painted.extend(
                MarkerCluster(left + cluster.x, cluster.points, y)
                for cluster in cluster_points(by_domain[domain], scale, width)
            )
            self._paint_intervals(painter, scale, left, width, y, muted)
        self.clusters = tuple(painted)
        for index, cluster in enumerate(self.clusters):
            y = cluster.y
            selected = any(point.event_id == self.selected_event_id for point in cluster.points)
            painter.setPen(QPen(accent if selected else text, 2))
            painter.setBrush(accent if selected else self.palette().color(QPalette.ColorRole.Base))
            painter.drawEllipse(QPointF(cluster.x, y), 7, 7)
            if len(cluster.points) > 1:
                painter.setPen(text)
                painter.drawText(QRectF(cluster.x - 12, y - 31, 24, 18), Qt.AlignmentFlag.AlignCenter, str(len(cluster.points)))
            representative = cluster.points[0].event
            label_y = y + 18 if index % 2 == 0 else y + 56
            painter.setPen(text)
            painter.drawText(QRectF(cluster.x - 70, label_y, 140, 18), Qt.AlignmentFlag.AlignCenter, representative.title[:28])
            painter.setPen(muted)
            painter.drawText(QRectF(cluster.x - 70, label_y + 20, 140, 18), Qt.AlignmentFlag.AlignCenter, format_temporal(representative).split(" (")[0])

    def _paint_intervals(self, painter: QPainter, scale: TemporalScale, left: float, width: float, y: float, color) -> None:
        for interval in self.presentation.intervals:
            start, end = scale.position(interval.start), scale.position(interval.end)
            if start is None or end is None:
                continue
            x1, x2 = left + start * width, left + end * width
            painter.setPen(QPen(color, 6))
            painter.drawLine(QPointF(x1, y - 50), QPointF(x2, y - 50))
            painter.setPen(QPen(color, 1))
            painter.drawLine(QPointF(x1, y - 58), QPointF(x1, y - 42))
            painter.drawLine(QPointF(x2, y - 58), QPointF(x2, y - 42))
            painter.drawText(QRectF(x1, y - 82, max(80.0, x2 - x1), 20), interval.label)

    def mousePressEvent(self, event) -> None:
        if self.clusters:
            nearest = min(self.clusters, key=lambda cluster: abs(cluster.x - event.position().x()) + abs(cluster.y - event.position().y()))
            if abs(nearest.x - event.position().x()) <= 16 and abs(nearest.y - event.position().y()) <= 20:
                event_id = nearest.points[0].event_id
                self.set_selected_event(event_id)
                self.event_selected.emit(event_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if self.selected_event_id:
            self.details_requested.emit(self.selected_event_id)
        super().mouseDoubleClickEvent(event)

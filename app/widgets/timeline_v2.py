from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models.timeline_event import TimelineEvent
from app.presentation.timeline import (
    TemporalScale,
    TimelineCategory,
    TimelineDisplayEvent,
    TimelinePoint,
    TimelinePresentation,
)
from app.ui.theme import LIGHT_THEME, ThemeTokens


_PRECISION_LABELS = {
    "year": "ano",
    "month": "mês",
    "day": "dia",
    "minute": "minuto",
    "second": "segundo",
    "millisecond": "milissegundo",
    "microsecond": "microssegundo",
    None: "não determinada",
}
_SOURCE_LABELS = {
    "metadata": "Metadados internos",
    "filesystem_metadata": "Metadados de filesystem",
    "digital_signature": "Assinatura PDF",
    "trusted_timestamp": "Timestamp confiável",
    "native": "Texto nativo",
    "native_partial": "Texto nativo parcial",
    "ocr": "OCR",
    "text": "Texto extraído",
    "filesystem": "Filesystem",
    "processing": "Processamento ForensiHash",
    "pdf_structure": "Estrutura PDF",
    "json": "JSON estruturado",
}


def format_temporal(event: TimelineEvent) -> str:
    """Format only the precision and timezone explicitly carried by an event."""
    value = event.date
    if value is None:
        return event.raw_timestamp or "Data não determinada"
    formats = {
        "year": "%Y",
        "month": "%m/%Y",
        "day": "%d/%m/%Y",
        "minute": "%d/%m/%Y · %H:%M",
        "second": "%d/%m/%Y · %H:%M:%S",
        "millisecond": "%d/%m/%Y · %H:%M:%S.%f",
        "microsecond": "%d/%m/%Y · %H:%M:%S.%f",
    }
    text = value.strftime(formats.get(event.precision, "%d/%m/%Y · %H:%M:%S"))
    if event.precision == "millisecond":
        text = text[:-3]
    if event.timezone_status == "explicit" and event.timezone:
        text += f" {event.timezone}"
    return text


def timezone_label(event: TimelineEvent) -> str:
    if event.timezone_status == "explicit":
        return event.timezone or "explícito"
    if event.timezone_status == "unknown":
        return "não informado"
    return "não aplicável"


def source_label(event: TimelineEvent) -> str:
    return _SOURCE_LABELS.get(
        event.source_type, event.source_type.replace("_", " ").title(),
    )


class TimelineEventRow(QFrame):
    selected = Signal(str)
    source_requested = Signal(str)

    def __init__(self, display: TimelineDisplayEvent, *, last: bool = False) -> None:
        super().__init__()
        self.display = display
        self.timeline_event = display.event
        self.setObjectName("TimelineV2EventRow")
        self.setProperty("timelineCategory", display.category.key)
        self.setProperty("selected", False)
        self.setAccessibleName(
            f"{display.category.label}, {display.title}, "
            f"{format_temporal(display.event)}"
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 6, 0)
        layout.setSpacing(12)

        rail = QWidget()
        rail.setObjectName("TimelineVerticalRail")
        rail.setFixedWidth(30)
        rail_layout = QVBoxLayout(rail)
        rail_layout.setContentsMargins(0, 13, 0, 0)
        rail_layout.setSpacing(3)
        marker = QLabel(display.category.marker)
        marker.setObjectName("TimelineV2Marker")
        marker.setProperty("timelineCategory", display.category.key)
        marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
        marker.setAccessibleName(display.category.label)
        line = QFrame()
        line.setObjectName("TimelineVerticalLineV2")
        line.setVisible(not last)
        rail_layout.addWidget(marker, alignment=Qt.AlignmentFlag.AlignHCenter)
        rail_layout.addWidget(line, stretch=1, alignment=Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(rail)

        content = QVBoxLayout()
        content.setContentsMargins(0, 11, 0, 12)
        content.setSpacing(3)

        category = QLabel(display.category.label)
        category.setObjectName("TimelineV2Category")
        category.setProperty("timelineCategory", display.category.key)
        title = QLabel(display.title)
        title.setObjectName("TimelineV2EventTitle")
        title.setWordWrap(True)
        observed = QLabel(format_temporal(display.event))
        observed.setObjectName("TimelineV2EventTime")
        origin = QLabel(
            f"{source_label(display.event)} · {display.event.source_engine}"
        )
        origin.setObjectName("TimelineV2Secondary")
        origin.setWordWrap(True)
        facts = QLabel(
            f"Precisão: {_PRECISION_LABELS.get(display.event.precision, display.event.precision)}"
            f" · Timezone: {timezone_label(display.event)}"
        )
        facts.setObjectName("TimelineV2Secondary")
        facts.setWordWrap(True)
        content.addWidget(category)
        content.addWidget(title)
        content.addWidget(observed)
        content.addWidget(origin)
        content.addWidget(facts)

        self.technical_panel = QWidget()
        self.technical_panel.setObjectName("TimelineTechnicalPanel")
        technical_layout = QVBoxLayout(self.technical_panel)
        technical_layout.setContentsMargins(10, 7, 10, 7)
        technical_layout.setSpacing(3)
        for label, value in event_detail_rows(display):
            detail = QLabel(f"{label}: {value}")
            detail.setObjectName("TimelineV2Technical")
            detail.setWordWrap(True)
            detail.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            technical_layout.addWidget(detail)
        self.technical_panel.setVisible(False)
        content.addWidget(self.technical_panel)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 3, 0, 0)
        details = QPushButton("Detalhes técnicos")
        details.setObjectName("TimelineDetailsButton")
        details.setCheckable(True)
        details.setAccessibleName(f"Detalhes técnicos de {display.title}")
        details.toggled.connect(self.technical_panel.setVisible)
        source = QPushButton("Ver fonte")
        source.setObjectName("TimelineSourceButton")
        source.setAccessibleName(f"Ver fonte de {display.title}")
        source.clicked.connect(
            lambda: self.source_requested.emit(display.event_id)
        )
        actions.addWidget(details)
        actions.addWidget(source)
        actions.addStretch()
        content.addLayout(actions)
        layout.addLayout(content, stretch=1)

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        self.selected.emit(self.timeline_event.event_id)
        super().mousePressEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self.selected.emit(self.timeline_event.event_id)
            event.accept()
            return
        super().keyPressEvent(event)


class DetailedTimeline(QWidget):
    event_selected = Signal(str)
    source_requested = Signal(str)
    INITIAL_RENDER_LIMIT = 200

    def __init__(self) -> None:
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        self.scroll = QScrollArea()
        self.scroll.setObjectName("DetailedTimelineScroll")
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.container = QWidget()
        self.container.setObjectName("DetailedTimelineContainer")
        self.items = QVBoxLayout(self.container)
        self.items.setContentsMargins(0, 0, 0, 0)
        self.items.setSpacing(0)
        self.scroll.setWidget(self.container)
        root.addWidget(self.scroll)
        self._presentation: TimelinePresentation | None = None
        self._references_visible = False
        self._render_limit = self.INITIAL_RENDER_LIMIT
        self._selected_event_id: str | None = None
        self.rows: dict[str, TimelineEventRow] = {}

    @property
    def rendered_event_count(self) -> int:
        return len(self.rows)

    def set_presentation(self, presentation: TimelinePresentation) -> None:
        changed = (
            self._presentation is None
            or self._presentation.artifact_id != presentation.artifact_id
        )
        self._presentation = presentation
        if changed:
            self._render_limit = self.INITIAL_RENDER_LIMIT
            self._references_visible = False
        self._render()

    def select_event(self, event_id: str | None) -> None:
        self._selected_event_id = event_id
        for row_id, row in self.rows.items():
            row.set_selected(row_id == event_id)
        row = self.rows.get(event_id or "")
        if row is not None:
            row.setFocus(Qt.FocusReason.OtherFocusReason)
            self.scroll.ensureWidgetVisible(row)

    def _render(self) -> None:
        self._clear()
        presentation = self._presentation
        if presentation is None:
            return
        points = presentation.primary_points
        visible = points[: self._render_limit]
        if not points:
            empty = QLabel("Nenhum evento temporal primário disponível.")
            empty.setObjectName("TimelineV2Empty")
            self.items.addWidget(empty)
        for index, point in enumerate(visible):
            display = presentation.display_event(point.event_id)
            if display is None:
                continue
            row = self._add_row(display, last=index == len(visible) - 1)
            self.rows[display.event_id] = row
        remaining = len(points) - len(visible)
        if remaining > 0:
            more = QPushButton(f"Mostrar mais eventos ({remaining} restantes)")
            more.setObjectName("TimelineMoreButton")
            more.clicked.connect(self._show_more)
            self.items.addWidget(more)

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
                display = presentation.display_event(event.event_id)
                if display is None:
                    continue
                row = self._add_row(display)
                self.rows[display.event_id] = row
            remaining_references = len(presentation.other_references) - 100
            if remaining_references > 0:
                note = QLabel(
                    f"{remaining_references} referência(s) adicionais não renderizadas."
                )
                note.setObjectName("TimelineV2Empty")
                self.items.addWidget(note)
        self.items.addStretch()
        self.select_event(self._selected_event_id)

    def _add_row(
        self, display: TimelineDisplayEvent, *, last: bool = False,
    ) -> TimelineEventRow:
        row = TimelineEventRow(display, last=last)
        row.selected.connect(self.event_selected)
        row.source_requested.connect(self.source_requested)
        self.items.addWidget(row)
        return row

    def _show_more(self) -> None:
        self._render_limit += self.INITIAL_RENDER_LIMIT
        self._render()

    def _toggle_references(self, checked: bool) -> None:
        self._references_visible = checked
        self._render()

    def _clear(self) -> None:
        self.rows.clear()
        while self.items.count():
            item = self.items.takeAt(0)
            if item.widget():
                item.widget().deleteLater()


@dataclass(frozen=True, slots=True)
class MarkerCluster:
    x: float
    points: tuple[TimelinePoint, ...]
    y: float = 0.0


def cluster_points(
    points: tuple[TimelinePoint, ...],
    scale: TemporalScale,
    width: float,
    threshold: float = 44.0,
) -> tuple[MarkerCluster, ...]:
    """Cluster sorted pixel positions in O(n log n), preserving every point."""
    positioned = sorted(
        (
            (normalized * width, point)
            for point in points
            if (normalized := scale.position(point)) is not None
        ),
        key=lambda item: (item[0], item[1].event_id),
    )
    grouped: list[tuple[list[TimelinePoint], float, float]] = []
    for x, point in positioned:
        if grouped and x - grouped[-1][2] <= threshold:
            values, total, _last_x = grouped[-1]
            values.append(point)
            grouped[-1] = (values, total + x, x)
        else:
            grouped.append(([point], x, x))
    return tuple(
        MarkerCluster(total / len(group), tuple(group))
        for group, total, _last_x in grouped
    )


class TimelinePopover(QFrame):
    event_selected = Signal(str)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.setObjectName("TimelinePopover")
        self.setWindowFlags(Qt.WindowType.Widget)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMaximumWidth(420)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 12)
        self.layout.setSpacing(5)
        self.hide()

    def show_cluster(
        self,
        displays: tuple[TimelineDisplayEvent, ...],
        anchor: QPoint,
    ) -> None:
        self._clear()
        if len(displays) == 1:
            self._render_event(displays[0])
        else:
            heading = QLabel(f"GRUPO TEMPORAL · {len(displays)} EVENTOS")
            heading.setObjectName("TimelinePopoverCategory")
            self.layout.addWidget(heading)
            ordered = sorted(
                displays,
                key=lambda item: (
                    item.event.temporal_order_key or (2, (), ""), item.event_id,
                ),
            )
            for display in ordered[:12]:
                button = QPushButton(
                    f"{format_temporal(display.event)}  ·  {display.title}"
                )
                button.setObjectName("TimelinePopoverEvent")
                button.setProperty("timelineCategory", display.category.key)
                button.setAccessibleName(
                    f"Abrir detalhes de {display.title}, {format_temporal(display.event)}"
                )
                button.clicked.connect(
                    lambda _checked=False, item=display: self._select(item)
                )
                self.layout.addWidget(button)
            if len(ordered) > 12:
                note = QLabel(f"+ {len(ordered) - 12} eventos no mesmo grupo visual")
                note.setObjectName("TimelineV2Secondary")
                self.layout.addWidget(note)
            self._add_close()
        self._place(anchor)

    def _select(self, display: TimelineDisplayEvent) -> None:
        self.event_selected.emit(display.event_id)
        self._clear()
        self._render_event(display)
        self.adjustSize()
        self._clamp_current_position()

    def _render_event(self, display: TimelineDisplayEvent) -> None:
        category = QLabel(display.category.label)
        category.setObjectName("TimelinePopoverCategory")
        category.setProperty("timelineCategory", display.category.key)
        title = QLabel(display.title)
        title.setObjectName("TimelinePopoverTitle")
        title.setWordWrap(True)
        timestamp = QLabel(format_temporal(display.event))
        timestamp.setObjectName("TimelinePopoverTime")
        self.layout.addWidget(category)
        self.layout.addWidget(title)
        self.layout.addWidget(timestamp)
        for label, value in event_detail_rows(display):
            row = QLabel(f"{label}: {value}")
            row.setObjectName("TimelinePopoverDetail")
            row.setWordWrap(True)
            row.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )
            self.layout.addWidget(row)
        self._add_close()

    def _add_close(self) -> None:
        close = QPushButton("Fechar")
        close.setObjectName("TimelinePopoverClose")
        close.clicked.connect(self.hide)
        self.layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)

    def _place(self, anchor: QPoint) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.setFixedWidth(min(400, max(280, parent.width() - 28)))
        self.adjustSize()
        x = anchor.x() - self.width() // 2
        y = anchor.y() + 24
        if y + self.height() > parent.height() - 12:
            y = anchor.y() - self.height() - 24
        x = max(12, min(x, parent.width() - self.width() - 12))
        y = max(12, min(y, parent.height() - self.height() - 12))
        self.move(x, y)
        self.show()
        self.raise_()
        self.setFocus(Qt.FocusReason.MouseFocusReason)

    def _clamp_current_position(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(
            max(12, min(self.x(), parent.width() - self.width() - 12)),
            max(12, min(self.y(), parent.height() - self.height() - 12)),
        )

    def _clear(self) -> None:
        while self.layout.count():
            item = self.layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.hide()
            event.accept()
            return
        super().keyPressEvent(event)


class VisualTimeline(QWidget):
    event_selected = Signal(str)
    details_requested = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("VisualTimeline")
        self.setAccessibleName("Timeline visual proporcional")
        self.setMinimumHeight(580)
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding,
        )
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.presentation = TimelinePresentation((), (), (), ())
        self.selected_event_id: str | None = None
        self.clusters: tuple[MarkerCluster, ...] = ()
        self.tokens = LIGHT_THEME
        self.popover = TimelinePopover(self)
        self.popover.event_selected.connect(self._select_from_popover)

    def apply_theme(self, tokens: ThemeTokens) -> None:
        self.tokens = tokens
        self.update()

    def set_presentation(self, presentation: TimelinePresentation) -> None:
        self.presentation = presentation
        valid_ids = {event.event_id for event in presentation.canonical_events}
        if self.selected_event_id not in valid_ids:
            self.selected_event_id = None
        self.popover.hide()
        self.update()

    def set_selected_event(self, event_id: str | None) -> None:
        self.selected_event_id = event_id
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        text = QColor(self.tokens.text_primary)
        muted = QColor(self.tokens.timeline_secondary)
        axis = QColor(self.tokens.timeline_axis)
        grid = QColor(self.tokens.timeline_grid)
        left, right = 68.0, max(69.0, self.width() - 68.0)
        width = right - left
        points = self.presentation.primary_points
        by_domain = {
            domain: tuple(point for point in points if point.domain == domain)
            for domain in ("instant", "civil")
        }
        interval_domains = {
            interval.start.domain for interval in self.presentation.intervals
        }
        available = [
            domain for domain in ("instant", "civil")
            if by_domain[domain] or domain in interval_domains
        ]
        if not available:
            painter.setPen(text)
            painter.drawText(
                QRectF(left, 100, width, 40),
                Qt.AlignmentFlag.AlignCenter,
                "Sem eventos temporalmente comparáveis",
            )
            self.clusters = ()
            return
        painted: list[MarkerCluster] = []
        for lane, domain in enumerate(available):
            # Keep the complete two-line marker caption clear of the next lane
            # heading at every supported font scale.
            y = 174.0 + lane * 280.0
            scale_points = list(by_domain[domain])
            scale_points.extend(
                point
                for interval in self.presentation.intervals
                for point in (interval.start, interval.end)
                if point.domain == domain
            )
            scale = TemporalScale.for_points(scale_points)
            if scale is None:
                continue
            painter.setPen(muted)
            lane_title = (
                "INSTANTES COM TIMEZONE"
                if domain == "instant"
                else "TEMPO CIVIL · TIMEZONE NÃO INFORMADO"
            )
            painter.drawText(QRectF(left, y - 154, width, 18), lane_title)
            self._paint_intervals(painter, scale, left, width, y)
            painter.setPen(QPen(axis, 1.4))
            painter.drawLine(QPointF(left, y), QPointF(right, y))
            self._paint_ticks(painter, scale, left, width, y, grid, muted)
            painted.extend(
                MarkerCluster(left + cluster.x, cluster.points, y)
                for cluster in cluster_points(by_domain[domain], scale, width)
            )
        self.clusters = tuple(painted)
        for index, cluster in enumerate(self.clusters):
            self._paint_cluster(painter, cluster, index, text, muted)

    def _paint_ticks(
        self,
        painter: QPainter,
        scale: TemporalScale,
        left: float,
        width: float,
        y: float,
        grid: QColor,
        muted: QColor,
    ) -> None:
        for tick in scale.ticks(5 if width >= 620 else 3):
            x = left + tick.position * width
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(x, y - 8), QPointF(x, y + 9))
            painter.setPen(muted)
            alignment = Qt.AlignmentFlag.AlignCenter
            rect = QRectF(x - 55, y + 11, 110, 18)
            if tick.position == 0:
                rect = QRectF(x, y + 11, 110, 18)
                alignment = Qt.AlignmentFlag.AlignLeft
            elif tick.position == 1:
                rect = QRectF(x - 110, y + 11, 110, 18)
                alignment = Qt.AlignmentFlag.AlignRight
            painter.drawText(rect, alignment, tick.label)

    def _paint_intervals(
        self,
        painter: QPainter,
        scale: TemporalScale,
        left: float,
        width: float,
        y: float,
    ) -> None:
        color = QColor(self.tokens.timeline_certificate)
        muted = QColor(self.tokens.timeline_secondary)
        for interval in self.presentation.intervals:
            start, end = scale.position(interval.start), scale.position(interval.end)
            if start is None or end is None:
                continue
            x1, x2 = left + start * width, left + end * width
            interval_y = y - 78
            painter.setPen(color)
            painter.drawText(
                QRectF(left, y - 132, width, 18),
                Qt.AlignmentFlag.AlignLeft,
                interval.label,
            )
            painter.setPen(QPen(color, 6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(QPointF(x1, interval_y), QPointF(x2, interval_y))
            painter.setPen(QPen(color, 1.3))
            painter.drawLine(QPointF(x1, interval_y - 9), QPointF(x1, interval_y + 9))
            painter.drawLine(QPointF(x2, interval_y - 9), QPointF(x2, interval_y + 9))
            painter.setPen(muted)
            start_text = f"Início · {format_temporal(interval.start.event)}"
            end_text = f"Expiração · {format_temporal(interval.end.event)}"
            painter.drawText(
                QRectF(x1, interval_y - 28, max(150.0, width / 2), 18),
                Qt.AlignmentFlag.AlignLeft,
                start_text,
            )
            painter.drawText(
                QRectF(max(left, x2 - max(180.0, width / 2)), interval_y - 28,
                       max(180.0, width / 2), 18),
                Qt.AlignmentFlag.AlignRight,
                end_text,
            )
            relation = next(
                (
                    item.relation for item in interval.verifications
                    if item.rule_id == "case.signing_time_certificate_validity"
                    and item.relation
                ),
                None,
            )
            if relation:
                painter.drawText(
                    QRectF(left, interval_y + 11, width, 18),
                    Qt.AlignmentFlag.AlignLeft,
                    f"Relação temporal observada · {relation}",
                )

    def _paint_cluster(
        self,
        painter: QPainter,
        cluster: MarkerCluster,
        index: int,
        text: QColor,
        muted: QColor,
    ) -> None:
        selected = any(
            point.event_id == self.selected_event_id for point in cluster.points
        )
        categories = {
            self._display(point.event_id).category.key
            for point in cluster.points
            if self._display(point.event_id) is not None
        }
        category_key = next(iter(categories)) if len(categories) == 1 else "other"
        color = self._category_color(category_key)
        if selected:
            painter.setPen(QPen(QColor(self.tokens.border_strong), 2))
            painter.setBrush(QColor(self.tokens.surface_elevated))
            painter.drawEllipse(QPointF(cluster.x, cluster.y), 11, 11)
        painter.setPen(QPen(color, 2))
        painter.setBrush(QColor(self.tokens.surface_elevated))
        self._draw_marker(painter, cluster.x, cluster.y, category_key)

        if len(cluster.points) > 1:
            badge = QRectF(cluster.x - 30, cluster.y - 39, 60, 22)
            painter.setPen(QPen(text, 1))
            painter.setBrush(QColor(self.tokens.surface_secondary))
            painter.drawRoundedRect(badge, 3, 3)
            painter.drawText(
                badge, Qt.AlignmentFlag.AlignCenter,
                f"{len(cluster.points)} eventos",
            )
        representative = cluster.points[0].event
        display = self._display(representative.event_id)
        title = display.title if display else representative.title
        label_y = cluster.y + (37 if index % 2 == 0 else 78)
        label_width = min(220.0, max(148.0, self.width() - 136.0))
        left_edge, right_edge = 68.0, max(69.0, self.width() - 68.0)
        if cluster.x - left_edge < label_width / 2:
            label_rect = QRectF(left_edge, label_y, label_width, 18)
            label_alignment = Qt.AlignmentFlag.AlignLeft
        elif right_edge - cluster.x < label_width / 2:
            label_rect = QRectF(right_edge - label_width, label_y, label_width, 18)
            label_alignment = Qt.AlignmentFlag.AlignRight
        else:
            label_rect = QRectF(
                cluster.x - label_width / 2, label_y, label_width, 18,
            )
            label_alignment = Qt.AlignmentFlag.AlignCenter
        painter.setPen(text)
        metrics = painter.fontMetrics()
        painter.drawText(
            label_rect,
            label_alignment,
            metrics.elidedText(
                title, Qt.TextElideMode.ElideRight, round(label_width - 4),
            ),
        )
        painter.setPen(muted)
        time_rect = QRectF(
            label_rect.x(), label_rect.y() + 20, label_rect.width(), 18,
        )
        painter.drawText(
            time_rect,
            label_alignment,
            format_temporal(representative),
        )

    @staticmethod
    def _draw_marker(
        painter: QPainter, x: float, y: float, category: str,
    ) -> None:
        if category == "document":
            painter.drawPolygon(QPolygonF([
                QPointF(x, y - 8), QPointF(x + 8, y),
                QPointF(x, y + 8), QPointF(x - 8, y),
            ]))
        elif category == "signature":
            painter.drawRect(QRectF(x - 7, y - 7, 14, 14))
        elif category == "structural":
            painter.drawPolygon(QPolygonF([
                QPointF(x, y - 8), QPointF(x + 8, y + 7),
                QPointF(x - 8, y + 7),
            ]))
        else:
            painter.drawEllipse(QPointF(x, y), 7, 7)

    def _category_color(self, key: str) -> QColor:
        value = {
            "document": self.tokens.timeline_document,
            "signature": self.tokens.timeline_signature,
            "metadata": self.tokens.timeline_metadata,
            "filesystem": self.tokens.timeline_filesystem,
            "structural": self.tokens.timeline_structural,
            "fh": self.tokens.timeline_fh,
            "certificate": self.tokens.timeline_certificate,
            "reference": self.tokens.timeline_secondary,
            "other": self.tokens.timeline_axis,
        }.get(key, self.tokens.timeline_axis)
        return QColor(value)

    def _display(self, event_id: str) -> TimelineDisplayEvent | None:
        return self.presentation.display_event(event_id)

    def _nearest_cluster(self, position: QPointF) -> MarkerCluster | None:
        if not self.clusters:
            return None
        nearest = min(
            self.clusters,
            key=lambda cluster: (
                abs(cluster.x - position.x()) + abs(cluster.y - position.y())
            ),
        )
        if (
            abs(nearest.x - position.x()) <= 22
            and abs(nearest.y - position.y()) <= 24
        ):
            return nearest
        return None

    def _show_cluster(self, cluster: MarkerCluster) -> None:
        displays = tuple(
            display
            for point in cluster.points
            if (display := self._display(point.event_id)) is not None
        )
        if not displays:
            return
        self.set_selected_event(displays[0].event_id)
        self.event_selected.emit(displays[0].event_id)
        self.popover.show_cluster(
            displays, QPoint(round(cluster.x), round(cluster.y)),
        )

    def _select_from_popover(self, event_id: str) -> None:
        self.set_selected_event(event_id)
        self.event_selected.emit(event_id)

    def mousePressEvent(self, event) -> None:
        cluster = self._nearest_cluster(event.position())
        if cluster is not None:
            self._show_cluster(cluster)
            event.accept()
            return
        self.popover.hide()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        cluster = self._nearest_cluster(event.position())
        if cluster is None:
            self.setToolTip("")
        elif len(cluster.points) == 1:
            display = self._display(cluster.points[0].event_id)
            self.setToolTip(
                f"{display.title if display else cluster.points[0].event.title}\n"
                f"{format_temporal(cluster.points[0].event)}\nClique para detalhes"
            )
        else:
            self.setToolTip(
                f"{len(cluster.points)} eventos agrupados visualmente\n"
                "Clique para listar os eventos canônicos"
            )
        super().mouseMoveEvent(event)

    def keyPressEvent(self, event) -> None:
        if not self.clusters:
            super().keyPressEvent(event)
            return
        selected_index = next(
            (
                index for index, cluster in enumerate(self.clusters)
                if any(point.event_id == self.selected_event_id for point in cluster.points)
            ),
            0,
        )
        if event.key() in {Qt.Key.Key_Left, Qt.Key.Key_Right}:
            delta = -1 if event.key() == Qt.Key.Key_Left else 1
            target = self.clusters[
                max(0, min(len(self.clusters) - 1, selected_index + delta))
            ]
            self.set_selected_event(target.points[0].event_id)
            self.event_selected.emit(target.points[0].event_id)
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space}:
            self._show_cluster(self.clusters[selected_index])
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.popover.hide()
            event.accept()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self.popover.isVisible():
            self.popover._clamp_current_position()


def event_detail_rows(
    display: TimelineDisplayEvent,
) -> tuple[tuple[str, str], ...]:
    event = display.event
    rows: list[tuple[str, str]] = [
        ("Origem", source_label(event)),
        ("Source type", event.source_type),
        ("Provider/parser", event.source_engine),
        ("Precisão", _PRECISION_LABELS.get(event.precision, str(event.precision))),
        ("Timezone", timezone_label(event)),
    ]
    if display.semantic_role:
        rows.append(("Papel semântico", display.semantic_role))
    if event.raw_timestamp:
        rows.append(("Valor bruto", event.raw_timestamp))
    if event.field_path:
        rows.append(("Campo/locator", event.field_path))
    if event.page is not None:
        rows.append(("Página", str(event.page)))
    if event.offset is not None:
        rows.append(("Offset", str(event.offset)))
    if event.revision is not None:
        rows.append(("Revisão estrutural", str(event.revision)))
    for key, label in (
        ("metadata_group", "Grupo de metadata"),
        ("startxref_offset", "Offset startxref"),
        ("startxref_declared_offset", "Offset declarado"),
        ("eof_offset", "Offset EOF"),
        ("trailer_offset", "Offset trailer"),
        ("xref_type", "Tipo xref"),
    ):
        value = event.attributes.get(key)
        if value is not None:
            rows.append((label, str(value)))
    if event.context:
        rows.append(("Contexto", event.context))
    for verification in display.verifications:
        rows.append((
            f"Verificação relacionada · {verification.label}",
            verification.relation or verification.statement,
        ))
    if event.description:
        rows.append(("Observação técnica", event.description))
    if event.limitations:
        rows.append(("Limitação", " ".join(event.limitations)))
    return tuple(rows)

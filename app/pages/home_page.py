from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from app.ui.case_catalog import RecentCase
from app.ui.line_icons import HomeIllustration


class HomePage(QWidget):
    """Product entry point, independent from a currently opened case."""

    new_case_requested = Signal()
    open_case_requested = Signal()
    dropped_paths = Signal(list)
    recent_case_requested = Signal(object)
    recent_case_delete_requested = Signal(object)
    navigation_requested = Signal(str)
    open_file_requested = Signal()  # compatibility
    open_folder_requested = Signal()  # compatibility

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("HomePage")
        self.setAcceptDrops(True)
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setObjectName("HomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content.setObjectName("HomeContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(34, 30, 34, 36)
        layout.setSpacing(24)
        subtitle = QLabel("Inicie uma nova análise ou continue de onde parou.")
        subtitle.setObjectName("HomeSubtitle")
        layout.addWidget(subtitle)

        self.drop_area = QFrame()
        self.drop_area.setObjectName("HomeDropArea")
        drop_layout = QVBoxLayout(self.drop_area)
        drop_layout.setContentsMargins(28, 28, 28, 28)
        drop_layout.setSpacing(8)
        self.illustration = HomeIllustration()
        self.new_case_button = QPushButton("+  Criar novo Caso")
        self.new_case_button.setObjectName("HomeNewCaseButton")
        self.new_case_button.setAccessibleName("Criar novo Caso")
        self.new_case_button.clicked.connect(self.new_case_requested.emit)
        hint = QLabel("Selecione uma pasta ou arraste arquivos para começar uma nova análise.")
        hint.setObjectName("HomeDropHint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        self.open_case_button = QPushButton("Abrir Caso existente")
        self.open_case_button.setObjectName("HomeOpenCaseButton")
        self.open_case_button.clicked.connect(self.open_case_requested.emit)
        drop_layout.addWidget(self.illustration, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(self.new_case_button, alignment=Qt.AlignmentFlag.AlignCenter)
        drop_layout.addWidget(hint)
        drop_layout.addWidget(self.open_case_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.drop_area)

        section = QLabel("CASOS RECENTES")
        section.setObjectName("SectionLabel")
        layout.addWidget(section)
        self.recent_container = QWidget()
        self.recent_layout = QVBoxLayout(self.recent_container)
        self.recent_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_layout.setSpacing(0)
        layout.addWidget(self.recent_container)
        self.set_recent_cases([])

        section = QLabel("EXPLORE O FORENSIHASH")
        section.setObjectName("SectionLabel")
        layout.addWidget(section)
        self.explore_container = QWidget()
        explore = QVBoxLayout(self.explore_container)
        explore.setContentsMargins(0, 0, 0, 0)
        explore.setSpacing(0)
        for key, name, detail, requires_case in (
            ("correlations", "Correlações", "Explore relações técnicas observadas entre artefatos.", True),
            ("timeline", "Timeline", "Examine eventos e informações temporais do Caso.", True),
            ("deep_file_explorer", "Deep File Explorer", "Inspecione profundamente a estrutura interna de arquivos.", False),
        ):
            button = QPushButton(f"{name}\n{detail}" + (" · requer Caso aberto" if requires_case else ""))
            button.setObjectName("HomeExploreRow")
            button.setProperty("requiresCase", requires_case)
            button.clicked.connect(lambda checked=False, page=key: self.navigation_requested.emit(page))
            explore.addWidget(button)
        layout.addWidget(self.explore_container)

        tips_title = QLabel("DICAS RÁPIDAS")
        tips_title.setObjectName("SectionLabel")
        layout.addWidget(tips_title)
        self.tips_container = QFrame()
        self.tips_container.setObjectName("HomeTips")
        tips = QVBoxLayout(self.tips_container)
        tips.setContentsMargins(16, 8, 16, 8)
        tips.setSpacing(0)
        for title_text, detail in (
            ("Organize seus Casos", "Use nomes claros para localizar análises depois."),
            ("Explore correlações", "Veja relações técnicas observadas entre artefatos."),
            ("Use o Deep File Explorer", "Inspecione estruturas internas de arquivos."),
        ):
            tip = QLabel(f"<b>{title_text}</b><br><span>{detail}</span>")
            tip.setObjectName("HomeTip")
            tip.setWordWrap(True)
            tips.addWidget(tip)
        layout.addWidget(self.tips_container)
        layout.addStretch()
        scroll.setWidget(content)
        root.addWidget(scroll)

    def set_theme_mode(self, mode: str) -> None:
        """Compatibility hook; the shell owns the single primary brand mark."""

    def set_case_open(self, is_open: bool) -> None:
        for button in self.explore_container.findChildren(QPushButton):
            button.setEnabled(is_open or not bool(button.property("requiresCase")))

    def set_recent_cases(self, cases: list[RecentCase]) -> None:
        while self.recent_layout.count():
            item = self.recent_layout.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()
        if not cases:
            empty = QLabel("Nenhum Caso recente.\nCrie um novo Caso para começar.")
            empty.setObjectName("HomeRecentEmpty")
            self.recent_layout.addWidget(empty)
            return
        for recent in cases:
            try:
                accessed = datetime.fromisoformat(recent.last_opened).astimezone().strftime("%d/%m/%Y %H:%M")
            except ValueError:
                accessed = recent.last_opened
            card = QFrame()
            card.setObjectName("HomeRecentCaseCard")
            row = QHBoxLayout(card)
            row.setContentsMargins(0, 0, 4, 0)
            row.setSpacing(0)
            button = QPushButton(f"{recent.name}\n{recent.file_count} arquivo(s) · {accessed}")
            button.setObjectName("HomeRecentCase")
            button.setProperty("caseId", recent.case_id)
            button.setAccessibleName(f"Abrir Caso {recent.name}")
            button.clicked.connect(lambda checked=False, item=recent: self.recent_case_requested.emit(item))
            delete_button = QPushButton("×")
            delete_button.setObjectName("HomeRecentCaseDelete")
            delete_button.setProperty("caseId", recent.case_id)
            delete_button.setFixedSize(28, 28)
            delete_button.setToolTip("Excluir caso")
            delete_button.setAccessibleName("Excluir caso")
            delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
            delete_button.clicked.connect(
                lambda checked=False, item=recent: self.recent_case_delete_requested.emit(item)
            )
            row.addWidget(button, stretch=1)
            row.addWidget(delete_button, alignment=Qt.AlignmentFlag.AlignVCenter)
            self.recent_layout.addWidget(card)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls() and any(url.isLocalFile() for url in event.mimeData().urls()):
            self._drop_state(True)
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._drop_state(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:
        paths = [Path(url.toLocalFile()) for url in event.mimeData().urls() if url.isLocalFile()]
        self._drop_state(False)
        if paths:
            self.dropped_paths.emit(paths)
            event.acceptProposedAction()

    def _drop_state(self, active: bool) -> None:
        self.drop_area.setProperty("dropActive", active)
        self.style().unpolish(self.drop_area)
        self.style().polish(self.drop_area)

    def update_workspace(self, **_: object) -> None:
        """Compatibility hook; state now belongs to the stable shell."""

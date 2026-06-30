from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)


class SummaryCard(QWidget):
    """Card compacto do Resumo Pericial."""

    def __init__(self) -> None:
        super().__init__()

        self.title_label = QLabel("📋 Resumo Pericial")
        self.title_label.setObjectName("summaryTitle")

        self.score_label = QLabel("0/100")
        self.score_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setFixedHeight(8)

        self.badges_layout = QHBoxLayout()
        self.badges_layout.setSpacing(6)

        self.main_finding_label = QLabel("Nenhuma análise carregada.")
        self.main_finding_label.setObjectName("summaryText")
        self.main_finding_label.setWordWrap(True)

        self.expert_note_text = QLabel("")
        self.expert_note_text.setWordWrap(True)
        self.expert_note_text.setObjectName("expertNoteText")

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("summaryCard")
        card.setMaximumHeight(260)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(10)

        header = QHBoxLayout()
        header.addWidget(self.title_label)
        header.addStretch()
        header.addWidget(self.score_label)

        card_layout.addLayout(header)
        card_layout.addWidget(self.progress_bar)
        card_layout.addLayout(self.badges_layout)

        finding_title = QLabel("Principal achado")
        finding_title.setObjectName("summarySectionTitle")
        card_layout.addWidget(finding_title)
        card_layout.addWidget(self.main_finding_label)

        note_box = QFrame()
        note_box.setObjectName("expertNoteBox")

        note_layout = QVBoxLayout(note_box)
        note_layout.setContentsMargins(12, 10, 12, 10)
        note_layout.setSpacing(4)

        note_title = QLabel("🧠 O Perito Observa")
        note_title.setObjectName("expertNoteTitle")

        note_layout.addWidget(note_title)
        note_layout.addWidget(self.expert_note_text)

        card_layout.addWidget(note_box)

        main_layout.addWidget(card)

    def update_summary(self, summary: dict) -> None:
        score = int(summary.get("score", 0))
        risk_level = summary.get("risk_level", "Não definido")

        self.score_label.setText(f"{score}/100 • Risco {risk_level}")
        self.score_label.setObjectName(self._score_label_style(score))
        self._refresh_style(self.score_label)

        self.progress_bar.setValue(score)
        self.progress_bar.setObjectName(self._score_bar_style(score))
        self._refresh_style(self.progress_bar)

        self._clear_layout(self.badges_layout)

        for badge in summary.get("badges", [])[:4]:
            badge_label = QLabel(
                self._badge_text(
                    badge.get("label", ""),
                    badge.get("status", "neutral"),
                )
            )
            badge_label.setObjectName(f"badge_{badge.get('status', 'neutral')}")
            badge_label.setAlignment(Qt.AlignCenter)
            badge_label.setMinimumHeight(26)
            self.badges_layout.addWidget(badge_label)

        self.badges_layout.addStretch()

        findings = summary.get("findings", [])
        if findings:
            self.main_finding_label.setText(findings[0])
        else:
            self.main_finding_label.setText("Nenhum achado técnico relevante foi informado.")

        self.expert_note_text.setText(summary.get("expert_note", ""))

    def _clear_layout(self, layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    def _badge_text(self, label: str, status: str) -> str:
        icons = {
            "ok": "✓",
            "warning": "⚠",
            "danger": "!",
            "info": "i",
            "neutral": "•",
        }

        return f"{icons.get(status, '•')} {label}"

    def _score_label_style(self, score: int) -> str:
        if score >= 85:
            return "summaryScoreOk"
        if score >= 65:
            return "summaryScoreWarning"
        return "summaryScoreDanger"

    def _score_bar_style(self, score: int) -> str:
        if score >= 85:
            return "summaryProgressOk"
        if score >= 65:
            return "summaryProgressWarning"
        return "summaryProgressDanger"

    def _refresh_style(self, widget: QWidget) -> None:
        widget.style().unpolish(widget)
        widget.style().polish(widget)
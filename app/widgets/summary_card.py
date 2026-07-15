from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)


class SummaryCard(QWidget):
    """Card factual do resumo técnico."""

    def __init__(self) -> None:
        super().__init__()

        self.title_label = QLabel("📋 Resumo técnico factual")
        self.title_label.setObjectName("summaryTitle")

        self.facts_layout = QGridLayout()
        self.facts_layout.setHorizontalSpacing(18)
        self.facts_layout.setVerticalSpacing(6)

        self.note_label = QLabel(
            "Os resultados técnicos serão exibidos após a análise."
        )
        self.note_label.setWordWrap(True)
        self.note_label.setObjectName("expertNoteText")

        self._setup_ui()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        card = QFrame()
        card.setObjectName("summaryCard")

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 14, 18, 14)
        card_layout.setSpacing(10)
        card_layout.addWidget(self.title_label)
        card_layout.addLayout(self.facts_layout)
        card_layout.addWidget(self.note_label)

        main_layout.addWidget(card)

    def update_summary(self, summary: dict) -> None:
        self.title_label.setText(
            f"📋 {summary.get('title', 'Resumo técnico factual')}"
        )
        self._clear_layout(self.facts_layout)

        for row, (label, value) in enumerate(
            summary.get("facts", [])
        ):
            label_widget = QLabel(f"{label}:")
            label_widget.setObjectName("summarySectionTitle")
            value_widget = QLabel(str(value))
            value_widget.setObjectName("summaryText")
            value_widget.setWordWrap(True)
            self.facts_layout.addWidget(label_widget, row, 0)
            self.facts_layout.addWidget(value_widget, row, 1)

        self.note_label.setText(summary.get("note", ""))

    @staticmethod
    def _clear_layout(layout) -> None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

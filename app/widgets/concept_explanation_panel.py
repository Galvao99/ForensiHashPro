from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.knowledge.pdf_structure_concepts import PdfStructureConcept


class ConceptExplanationPanel(QFrame):
    close_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConceptExplanationPanel")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.setVisible(False)

        header = QHBoxLayout()
        self.title_label = QLabel()
        self.title_label.setObjectName("ConceptExplanationTitle")
        self.close_button = QPushButton("Fechar")
        self.close_button.setObjectName("ConceptExplanationClose")
        self.close_button.setCursor(Qt.PointingHandCursor)
        self.close_button.clicked.connect(self.close_requested.emit)
        header.addWidget(self.title_label, stretch=1)
        header.addWidget(self.close_button)

        self.description_label = QLabel()
        self.description_label.setObjectName("ConceptExplanationText")
        self.description_label.setWordWrap(True)
        self.description_label.setTextInteractionFlags(Qt.TextSelectableByMouse)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        layout.addLayout(header)
        layout.addWidget(self.description_label)

    def show_concept(self, concept: PdfStructureConcept) -> None:
        self.title_label.setText(concept.title)
        self.description_label.setText(concept.description)
        self.setVisible(True)

    def clear(self) -> None:
        self.title_label.clear()
        self.description_label.clear()
        self.setVisible(False)

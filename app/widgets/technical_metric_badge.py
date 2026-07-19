from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QWidget,
)


class TechnicalMetricBadge(QPushButton):
    """Badge clicável que apresenta um fato técnico sem interpretá-lo."""

    concept_requested = Signal(str)

    def __init__(
        self,
        value: str,
        label: str,
        concept_key: str,
        detected: bool | None = None,
        label_first: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.concept_key = concept_key
        self.setObjectName("TechnicalMetricBadge")
        self.setProperty("detected", detected)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 5, 9, 5)
        layout.setSpacing(5)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("TechnicalMetricValue")
        self.value_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label_label = QLabel(label)
        self.label_label.setObjectName("TechnicalMetricLabel")
        self.label_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.info_icon = QLabel("ⓘ")
        self.info_icon.setObjectName("TechnicalMetricInfoIcon")
        self.info_icon.setAttribute(Qt.WA_TransparentForMouseEvents)

        first, second = (
            (self.label_label, self.value_label)
            if label_first
            else (self.value_label, self.label_label)
        )
        layout.addWidget(first)
        layout.addWidget(second)
        layout.addWidget(self.info_icon)
        self.clicked.connect(self._request_concept)

    def _request_concept(self) -> None:
        self.concept_requested.emit(self.concept_key)

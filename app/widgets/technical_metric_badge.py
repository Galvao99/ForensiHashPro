from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
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
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumWidth(118)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(2)

        self.value_label = QLabel(value)
        self.value_label.setObjectName("TechnicalMetricValue")
        self.value_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.label_label = QLabel(label)
        self.label_label.setObjectName("TechnicalMetricLabel")
        self.label_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        # ``label_first`` permanece aceito para compatibilidade com chamadas
        # existentes. O novo contrato visual mantém valor e rótulo em linhas
        # previsíveis para evitar compressão e sobreposição.
        self.label_first = label_first
        layout.addWidget(self.value_label)
        layout.addWidget(self.label_label)
        self.clicked.connect(self._request_concept)

    def sizeHint(self) -> QSize:
        layout_hint = self.layout().sizeHint()
        return layout_hint.expandedTo(QSize(self.minimumWidth(), 58))

    def minimumSizeHint(self) -> QSize:
        layout_minimum = self.layout().minimumSize()
        return layout_minimum.expandedTo(QSize(self.minimumWidth(), 58))

    def _request_concept(self) -> None:
        self.concept_requested.emit(self.concept_key)

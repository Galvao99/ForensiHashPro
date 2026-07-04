from PySide6.QtCore import QDateTime, Signal
from PySide6 import QtWidgets


class ContractDateConfirmationCard(QtWidgets.QFrame):
    confirmed = Signal(object)

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("ContractDateConfirmationCard")
        self.event = None

        self.title = QtWidgets.QLabel("⚠ Possível data de pactuação detectada")
        self.title.setObjectName("ContractDateTitle")

        self.message = QtWidgets.QLabel()
        self.message.setWordWrap(True)
        self.message.setObjectName("ContractDateMessage")

        self.date_input = QtWidgets.QDateTimeEdit()
        self.date_input.setCalendarPopup(True)
        self.date_input.setDisplayFormat("dd/MM/yyyy HH:mm:ss")

        self.confirm_button = QtWidgets.QPushButton("Confirmar data")
        self.correct_button = QtWidgets.QPushButton("Corrigir com data informada")

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.date_input)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.confirm_button)
        buttons_layout.addWidget(self.correct_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)
        layout.addWidget(self.title)
        layout.addWidget(self.message)
        layout.addLayout(buttons_layout)

        self.confirm_button.clicked.connect(self.confirm_date)
        self.correct_button.clicked.connect(self.correct_date)

        self.setVisible(False)

    def set_event(self, event) -> None:
        self.event = event

        if not event:
            self.setVisible(False)
            return

        self.message.setText(
            f"O OCR/texto identificou uma possível data de pactuação: "
            f"<b>{event.formatted_date()}</b>.<br>"
            "Confirme se está correta ou informe manualmente a data real. "
            "A extração por OCR pode cometer erros de leitura."
        )

        if event.date:
            self.date_input.setDateTime(QDateTime(event.date))

        self.setVisible(True)

    def confirm_date(self) -> None:
        if not self.event:
            return

        self.event.confirmed = True
        self.event.needs_confirmation = False
        self.event.description = (
            "Data de pactuação confirmada pelo usuário. "
            "A data foi inicialmente sugerida por OCR/texto, sujeito a erro de leitura."
        )

        self.setVisible(False)
        self.confirmed.emit(self.event)

    def correct_date(self) -> None:
        if not self.event:
            return

        self.event.date = self.date_input.dateTime().toPython()
        self.event.confirmed = True
        self.event.needs_confirmation = False
        self.event.description = (
            "Data de pactuação corrigida manualmente pelo usuário. "
            "A data originalmente sugerida por OCR/texto pode conter erro de leitura."
        )

        self.setVisible(False)
        self.confirmed.emit(self.event)
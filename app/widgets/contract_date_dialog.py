from PySide6.QtCore import QDateTime
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class ContractDateDialog(QDialog):
    def __init__(self, detected_date, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Confirmar data de pactuação")
        self.selected_date = detected_date

        layout = QVBoxLayout(self)

        message = QLabel(
            "O ForensiHash identificou uma possível data contratual por OCR/texto.\n\n"
            "Confirme se a data está correta ou informe manualmente a data real.\n\n"
            "Atenção: OCR pode cometer erros de leitura."
        )
        message.setWordWrap(True)

        self.date_input = QDateTimeEdit()
        self.date_input.setCalendarPopup(True)

        if detected_date:
            self.date_input.setDateTime(QDateTime(detected_date))

        confirm_button = QPushButton("Confirmar data identificada")
        manual_button = QPushButton("Usar data informada")
        cancel_buttons = QDialogButtonBox(QDialogButtonBox.Cancel)

        layout.addWidget(message)
        layout.addWidget(self.date_input)
        layout.addWidget(confirm_button)
        layout.addWidget(manual_button)
        layout.addWidget(cancel_buttons)

        confirm_button.clicked.connect(self.accept_date)
        manual_button.clicked.connect(self.accept_date)
        cancel_buttons.rejected.connect(self.reject)

    def accept_date(self):
        self.selected_date = self.date_input.dateTime().toPython()
        self.accept()
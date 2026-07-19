from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class RawTechnicalDataPanel(QFrame):
    """
    Painel reutilizável para apresentação de texto técnico bruto.

    O painel não conhece modelos, parsers ou engines.
    Ele recebe somente uma string previamente formatada.
    """

    close_requested = Signal()
    copied = Signal()

    EMPTY_TEXT = "Nenhuma estrutura técnica disponível."

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._technical_text = ""

        self.setObjectName("RawTechnicalDataPanel")
        self.setVisible(False)

        self._build_ui()
        self._connect_signals()
        self.clear()

    def _build_ui(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(
            14,
            14,
            14,
            14,
        )
        root_layout.setSpacing(10)

        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        header_layout.setSpacing(8)

        self.title_label = QLabel(
            "Estrutura técnica"
        )
        self.title_label.setObjectName(
            "RawTechnicalTitle"
        )

        self.copy_button = QPushButton(
            "Copiar"
        )
        self.copy_button.setObjectName(
            "RawTechnicalCopyButton"
        )
        self.copy_button.setToolTip(
            "Copiar o conteúdo técnico"
        )

        self.close_button = QPushButton(
            "Fechar"
        )
        self.close_button.setObjectName(
            "RawTechnicalCloseButton"
        )
        self.close_button.setToolTip(
            "Fechar o painel técnico"
        )

        header_layout.addWidget(
            self.title_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.copy_button
        )
        header_layout.addWidget(
            self.close_button
        )

        self.text_view = QPlainTextEdit()
        self.text_view.setObjectName(
            "RawTechnicalText"
        )
        self.text_view.setReadOnly(True)
        self.text_view.setLineWrapMode(
            QPlainTextEdit.NoWrap
        )
        self.text_view.setMinimumHeight(
            280
        )

        fixed_font = QFontDatabase.systemFont(
            QFontDatabase.FixedFont
        )
        self.text_view.setFont(
            fixed_font
        )

        root_layout.addLayout(
            header_layout
        )
        root_layout.addWidget(
            self.text_view
        )

    def _connect_signals(self) -> None:
        self.copy_button.clicked.connect(
            self.copy_to_clipboard
        )

        self.close_button.clicked.connect(
            self.request_close
        )

    def set_text(
        self,
        text: str | None,
    ) -> None:
        """
        Define o conteúdo técnico exibido no painel.

        O texto é preservado exatamente como recebido para que
        o conteúdo copiado corresponda à saída do formatter.
        """

        normalized_text = text or ""

        self._technical_text = (
            normalized_text
        )

        self.text_view.setPlainText(
            normalized_text
            or self.EMPTY_TEXT
        )

        self.copy_button.setEnabled(
            bool(normalized_text)
        )

    def technical_text(self) -> str:
        """
        Retorna exatamente o texto técnico atualmente armazenado.
        """

        return self._technical_text

    def has_text(self) -> bool:
        """
        Informa se existe conteúdo técnico disponível.
        """

        return bool(self._technical_text)

    def open_panel(self) -> None:
        """
        Torna o painel visível.
        """

        if not self._technical_text:
            self.text_view.setPlainText(
                self.EMPTY_TEXT
            )

        self.setVisible(True)

    def close_panel(self) -> None:
        """
        Oculta o painel sem remover o conteúdo armazenado.
        """

        self.setVisible(False)

    def clear(self) -> None:
        """
        Remove o conteúdo técnico e retorna o painel ao estado vazio.
        """

        self._technical_text = ""

        self.text_view.setPlainText(
            self.EMPTY_TEXT
        )

        self.copy_button.setEnabled(
            False
        )

        self.close_panel()

    def request_close(self) -> None:
        """
        Fecha o painel e informa ao componente pai que o fechamento
        foi solicitado pelo usuário.
        """

        self.close_panel()
        self.close_requested.emit()

    def copy_to_clipboard(self) -> None:
        """
        Copia exatamente o texto técnico armazenado para o clipboard.
        """

        if not self._technical_text:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(
            self._technical_text
        )

        self.copied.emit()
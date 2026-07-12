from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class FileInvestigationPanel(QFrame):
    """
    Painel lateral responsável por apresentar informações
    do arquivo atualmente selecionado.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName("FileInvestigationPanel")

        self.setMinimumWidth(350)
        self.setMaximumWidth(440)

        self.setSizePolicy(
            QSizePolicy.Preferred,
            QSizePolicy.Maximum,
        )

        self.current_result: object | None = None
        self.available_hashes: dict[str, str] = {}

        self._build_ui()
        self._connect_signals()
        self.clear()

    def _build_ui(self) -> None:
        self.main_layout = QVBoxLayout(self)

        self.main_layout.setContentsMargins(
            18,
            18,
            18,
            18,
        )

        self.main_layout.setSpacing(14)

        # Impede o QScrollArea de comprimir os componentes.
        self.main_layout.setSizeConstraint(
            QLayout.SetMinimumSize
        )

        self.main_layout.setAlignment(
            Qt.AlignTop
        )

        title = QLabel("Arquivo analisado")
        title.setObjectName("InspectorTitle")

        self.file_name_label = QLabel(
            "Nenhum arquivo selecionado"
        )

        self.file_name_label.setObjectName(
            "InspectorFileName"
        )

        self.file_name_label.setWordWrap(True)

        self.file_name_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.file_name_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        self.main_layout.addWidget(title)
        self.main_layout.addWidget(
            self.file_name_label
        )

        self.main_layout.addWidget(
            self._create_separator()
        )

        # Caminho
        path_field, self.path_value = (
            self._create_multiline_field(
                title="Caminho",
                height=68,
            )
        )

        self.main_layout.addWidget(path_field)

        # Extensão e tamanho
        compact_container = QWidget()

        compact_container.setObjectName(
            "InspectorTransparentContainer"
        )

        compact_layout = QGridLayout(
            compact_container
        )

        compact_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        compact_layout.setHorizontalSpacing(10)
        compact_layout.setVerticalSpacing(0)

        compact_layout.setColumnStretch(0, 1)
        compact_layout.setColumnStretch(1, 1)

        extension_field, self.extension_value = (
            self._create_single_field(
                title="Extensão"
            )
        )

        size_field, self.size_value = (
            self._create_single_field(
                title="Tamanho"
            )
        )

        compact_layout.addWidget(
            extension_field,
            0,
            0,
        )

        compact_layout.addWidget(
            size_field,
            0,
            1,
        )

        self.main_layout.addWidget(
            compact_container
        )

        # Data da análise
        analyzed_field, self.analyzed_at_value = (
            self._create_single_field(
                title="Analisado em"
            )
        )

        self.main_layout.addWidget(
            analyzed_field
        )

        self.main_layout.addWidget(
            self._create_separator()
        )

        # Hash
        hash_title = QLabel("Hash do arquivo")

        hash_title.setObjectName(
            "InspectorSectionTitle"
        )

        self.main_layout.addWidget(hash_title)

        self.hash_combo = QComboBox()

        self.hash_combo.setObjectName(
            "InspectorHashCombo"
        )

        self.hash_combo.setFixedHeight(42)

        self.hash_combo.setFocusPolicy(
            Qt.NoFocus
        )

        self.main_layout.addWidget(
            self.hash_combo
        )

        self.hash_value = QPlainTextEdit()

        self.hash_value.setObjectName(
            "InspectorHashValue"
        )

        self.hash_value.setReadOnly(True)

        self.hash_value.setFixedHeight(76)

        self.hash_value.setLineWrapMode(
            QPlainTextEdit.WidgetWidth
        )

        self.hash_value.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.hash_value.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        self.hash_value.setFocusPolicy(
            Qt.ClickFocus
        )

        self.main_layout.addWidget(
            self.hash_value
        )

        self.copy_button = QPushButton(
            "Copiar hash"
        )

        self.copy_button.setObjectName(
            "InspectorCopyButton"
        )

        self.copy_button.setCursor(
            Qt.PointingHandCursor
        )

        self.copy_button.setFocusPolicy(
            Qt.NoFocus
        )

        self.copy_button.setEnabled(False)

        copy_row = QHBoxLayout()

        copy_row.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        copy_row.setSpacing(0)

        copy_row.addWidget(
            self.copy_button
        )

        copy_row.addStretch()

        self.main_layout.addLayout(
            copy_row
        )

        self.main_layout.addWidget(
            self._create_separator()
        )

        # Contexto técnico
        context_title = QLabel(
            "Contexto técnico"
        )

        context_title.setObjectName(
            "InspectorSectionTitle"
        )

        self.main_layout.addWidget(
            context_title
        )

        producer_field, self.producer_value = (
            self._create_multiline_field(
                title="Producer",
                height=64,
            )
        )

        creator_field, self.creator_value = (
            self._create_multiline_field(
                title="Creator",
                height=64,
            )
        )

        signature_field, self.signature_value = (
            self._create_multiline_field(
                title="Assinatura digital",
                height=68,
            )
        )

        signer_field, self.signer_value = (
            self._create_multiline_field(
                title="Signatário",
                height=84,
            )
        )

        self.main_layout.addWidget(
            producer_field
        )

        self.main_layout.addWidget(
            creator_field
        )

        self.main_layout.addWidget(
            signature_field
        )

        self.main_layout.addWidget(
            signer_field
        )

    def _connect_signals(self) -> None:
        self.hash_combo.currentTextChanged.connect(
            self._show_selected_hash
        )

        self.copy_button.clicked.connect(
            self._copy_hash
        )

    def _create_single_field(
        self,
        *,
        title: str,
    ) -> tuple[QWidget, QLineEdit]:
        container = QWidget()

        container.setObjectName(
            "InspectorInformationBlock"
        )

        container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        layout = QVBoxLayout(container)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(5)

        title_label = QLabel(title)

        title_label.setObjectName(
            "InspectorFieldTitle"
        )

        title_label.setFixedHeight(18)

        value = QLineEdit()

        value.setObjectName(
            "InspectorSingleValue"
        )

        value.setReadOnly(True)

        value.setFixedHeight(40)

        value.setFocusPolicy(
            Qt.ClickFocus
        )

        layout.addWidget(title_label)
        layout.addWidget(value)

        return container, value

    def _create_multiline_field(
        self,
        *,
        title: str,
        height: int,
    ) -> tuple[QWidget, QPlainTextEdit]:
        container = QWidget()

        container.setObjectName(
            "InspectorInformationBlock"
        )

        container.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Fixed,
        )

        layout = QVBoxLayout(container)

        layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )

        layout.setSpacing(5)

        title_label = QLabel(title)

        title_label.setObjectName(
            "InspectorFieldTitle"
        )

        title_label.setFixedHeight(18)

        value = QPlainTextEdit()

        value.setObjectName(
            "InspectorMultiValue"
        )

        value.setReadOnly(True)

        value.setFixedHeight(height)

        value.setLineWrapMode(
            QPlainTextEdit.WidgetWidth
        )

        value.setHorizontalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        value.setVerticalScrollBarPolicy(
            Qt.ScrollBarAlwaysOff
        )

        value.setFocusPolicy(
            Qt.ClickFocus
        )

        layout.addWidget(title_label)
        layout.addWidget(value)

        return container, value

    @staticmethod
    def _create_separator() -> QFrame:
        separator = QFrame()

        separator.setObjectName(
            "InspectorSeparator"
        )

        separator.setFrameShape(
            QFrame.HLine
        )

        separator.setFrameShadow(
            QFrame.Plain
        )

        separator.setFixedHeight(1)

        return separator

    def update_analysis(
        self,
        result: object | None,
    ) -> None:
        if result is None:
            self.clear()
            return

        self.current_result = result

        file_info = getattr(
            result,
            "file_info",
            None,
        )

        file_name = self._first_value(
            self._read_attribute(
                file_info,
                "name",
            ),
            "Arquivo sem nome",
        )

        file_path = self._first_value(
            self._read_attribute(
                file_info,
                "path",
            ),
            "Não informado",
        )

        extension = self._first_value(
            self._read_attribute(
                file_info,
                "extension",
                "suffix",
            ),
            self._extract_extension(
                file_path
            ),
        )

        size = self._first_value(
            self._read_attribute(
                file_info,
                "size",
                "size_bytes",
                "file_size",
            ),
            self._read_attribute(
                result,
                "size",
                "file_size",
            ),
        )

        analyzed_at = self._first_value(
            self._read_attribute(
                result,
                "analyzed_at",
                "analysis_date",
                "created_at",
            ),
            self._read_attribute(
                file_info,
                "analyzed_at",
                "analysis_date",
            ),
        )

        self.file_name_label.setText(
            str(file_name)
        )

        self.file_name_label.setToolTip(
            str(file_name)
        )

        self._set_plain_text(
            self.path_value,
            file_path,
        )

        self.extension_value.setText(
            self._format_extension(
                extension
            )
        )

        self.extension_value.setToolTip(
            self.extension_value.text()
        )

        self.size_value.setText(
            self._format_size(size)
        )

        self.size_value.setToolTip(
            self.size_value.text()
        )

        self.analyzed_at_value.setText(
            self._format_datetime(
                analyzed_at
            )
        )

        self.analyzed_at_value.setToolTip(
            self.analyzed_at_value.text()
        )

        self._update_hashes(result)
        self._update_metadata(result)
        self._update_signature(result)

        self.updateGeometry()

    def _update_hashes(
        self,
        result: object,
    ) -> None:
        self.available_hashes.clear()

        hash_source = self._first_value(
            self._read_attribute(
                result,
                "hash_result",
                "hashes",
                "calculated_hashes",
            ),
            result,
        )

        possible_hashes = {
            "MD5": self._read_attribute(
                hash_source,
                "md5",
                "md5_hash",
            ),
            "SHA-1": self._read_attribute(
                hash_source,
                "sha1",
                "sha_1",
                "sha1_hash",
            ),
            "SHA-224": self._read_attribute(
                hash_source,
                "sha224",
                "sha_224",
                "sha224_hash",
            ),
            "SHA-256": self._read_attribute(
                hash_source,
                "sha256",
                "sha_256",
                "sha256_hash",
            ),
            "SHA-384": self._read_attribute(
                hash_source,
                "sha384",
                "sha_384",
                "sha384_hash",
            ),
            "SHA-512": self._read_attribute(
                hash_source,
                "sha512",
                "sha_512",
                "sha512_hash",
            ),
        }

        self.hash_combo.blockSignals(True)
        self.hash_combo.clear()

        for algorithm, value in possible_hashes.items():
            if value not in (
                None,
                "",
            ):
                self.available_hashes[
                    algorithm
                ] = str(value)

                self.hash_combo.addItem(
                    algorithm
                )

        self.hash_combo.blockSignals(False)

        if not self.available_hashes:
            self.hash_value.setPlainText(
                "Hash não disponível"
            )

            self.copy_button.setEnabled(False)
            return

        preferred_index = (
            self.hash_combo.findText(
                "SHA-256"
            )
        )

        self.hash_combo.setCurrentIndex(
            preferred_index
            if preferred_index >= 0
            else 0
        )

        self._show_selected_hash(
            self.hash_combo.currentText()
        )

    def _update_metadata(
        self,
        result: object,
    ) -> None:
        metadata_result = self._first_value(
            self._read_attribute(
                result,
                "metadata_result",
                "metadata",
            ),
            {},
        )

        producer = self._read_attribute(
            metadata_result,
            "producer",
            "pdf_producer",
        )

        creator = self._read_attribute(
            metadata_result,
            "creator",
            "pdf_creator",
        )

        raw_metadata = self._read_attribute(
            metadata_result,
            "raw",
            "metadata",
            "raw_metadata",
            "data",
        )

        if isinstance(
            raw_metadata,
            dict,
        ):
            producer = (
                producer
                or self._find_dictionary_value(
                    raw_metadata,
                    "Producer",
                    "PDF:Producer",
                )
            )

            creator = (
                creator
                or self._find_dictionary_value(
                    raw_metadata,
                    "Creator",
                    "PDF:Creator",
                )
            )

        self._set_plain_text(
            self.producer_value,
            producer,
        )

        self._set_plain_text(
            self.creator_value,
            creator,
        )

    def _update_signature(
        self,
        result: object,
    ) -> None:
        signature_result = self._read_attribute(
            result,
            "digital_signature_result",
            "signature_result",
            "digital_signature",
        )

        has_signature = self._read_attribute(
            signature_result,
            "has_signature",
            "is_signed",
            "signed",
        )

        is_valid = self._read_attribute(
            signature_result,
            "is_valid",
            "valid",
            "signature_valid",
        )

        signer = self._read_attribute(
            signature_result,
            "signer",
            "signer_name",
            "subject",
            "certificate_subject",
        )

        signatures = self._read_attribute(
            signature_result,
            "signatures",
        )

        if isinstance(
            signatures,
            list,
        ) and signatures:
            first_signature = signatures[0]

            signer = (
                signer
                or self._read_attribute(
                    first_signature,
                    "signer",
                    "signer_name",
                    "subject",
                    "certificate_subject",
                )
            )

            if has_signature is None:
                has_signature = True

            if is_valid is None:
                is_valid = self._read_attribute(
                    first_signature,
                    "is_valid",
                    "valid",
                    "signature_valid",
                )

        if has_signature is True:
            if is_valid is True:
                status = (
                    "Assinatura identificada e válida."
                )

            elif is_valid is False:
                status = (
                    "Assinatura identificada, "
                    "mas não validada."
                )

            else:
                status = (
                    "Assinatura identificada."
                )

        elif has_signature is False:
            status = (
                "Nenhuma assinatura digital "
                "identificada."
            )

        else:
            status = (
                "Não foi possível determinar."
            )

        self.signature_value.setPlainText(
            status
        )

        self._set_plain_text(
            self.signer_value,
            signer,
        )

    def _show_selected_hash(
        self,
        algorithm: str,
    ) -> None:
        hash_value = self.available_hashes.get(
            algorithm
        )

        if not hash_value:
            self.hash_value.setPlainText(
                "Hash não disponível"
            )

            self.copy_button.setEnabled(False)
            return

        self.hash_value.setPlainText(
            hash_value
        )

        self.hash_value.setToolTip(
            hash_value
        )

        self.copy_button.setEnabled(True)

    def _copy_hash(self) -> None:
        hash_value = self.available_hashes.get(
            self.hash_combo.currentText()
        )

        if not hash_value:
            return

        QGuiApplication.clipboard().setText(
            hash_value
        )

        self.copy_button.setText(
            "Copiado"
        )

        QTimer.singleShot(
            1200,
            lambda: self.copy_button.setText(
                "Copiar hash"
            ),
        )

    def clear(self) -> None:
        self.current_result = None
        self.available_hashes.clear()

        self.file_name_label.setText(
            "Nenhum arquivo selecionado"
        )

        self.path_value.setPlainText(
            "Não informado"
        )

        self.extension_value.setText(
            "Não informado"
        )

        self.size_value.setText(
            "Não informado"
        )

        self.analyzed_at_value.setText(
            "Não informado"
        )

        self.producer_value.setPlainText(
            "Não informado"
        )

        self.creator_value.setPlainText(
            "Não informado"
        )

        self.signature_value.setPlainText(
            "Não foi possível determinar."
        )

        self.signer_value.setPlainText(
            "Não informado"
        )

        self.hash_combo.blockSignals(True)
        self.hash_combo.clear()
        self.hash_combo.blockSignals(False)

        self.hash_value.setPlainText(
            "Hash não disponível"
        )

        self.copy_button.setEnabled(False)

    @staticmethod
    def _set_plain_text(
        widget: QPlainTextEdit,
        value: Any,
        fallback: str = "Não informado",
    ) -> None:
        text = (
            str(value)
            if value not in (
                None,
                "",
            )
            else fallback
        )

        widget.setPlainText(text)

        widget.setToolTip(
            ""
            if text == fallback
            else text
        )

    @staticmethod
    def _read_attribute(
        source: Any,
        *names: str,
    ) -> Any:
        if source is None:
            return None

        if isinstance(source, dict):
            for name in names:
                value = source.get(name)

                if value not in (
                    None,
                    "",
                ):
                    return value

            return None

        for name in names:
            value = getattr(
                source,
                name,
                None,
            )

            if value not in (
                None,
                "",
            ):
                return value

        return None

    @staticmethod
    def _first_value(
        *values: Any,
    ) -> Any:
        for value in values:
            if value not in (
                None,
                "",
            ):
                return value

        return None

    @staticmethod
    def _find_dictionary_value(
        values: dict[str, Any],
        *keys: str,
    ) -> Any:
        normalized = {
            str(key).lower(): value
            for key, value in values.items()
        }

        for key in keys:
            value = normalized.get(
                key.lower()
            )

            if value not in (
                None,
                "",
            ):
                return value

        return None

    @staticmethod
    def _extract_extension(
        file_path: Any,
    ) -> str | None:
        if not file_path:
            return None

        return Path(
            str(file_path)
        ).suffix

    @staticmethod
    def _format_extension(
        value: Any,
    ) -> str:
        if value in (
            None,
            "",
        ):
            return "Não informado"

        text = str(value).strip()

        if text.startswith("."):
            text = text[1:]

        return (
            text.upper()
            or "Não informado"
        )

    @staticmethod
    def _format_size(
        value: Any,
    ) -> str:
        if value in (
            None,
            "",
        ):
            return "Não informado"

        try:
            size = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return str(value)

        units = (
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        )

        for unit in units:
            if (
                size < 1024
                or unit == units[-1]
            ):
                if unit == "B":
                    return (
                        f"{int(size)} {unit}"
                    )

                return (
                    f"{size:.2f} {unit}"
                )

            size /= 1024

        return str(value)

    @staticmethod
    def _format_datetime(
        value: Any,
    ) -> str:
        if value in (
            None,
            "",
        ):
            return "Não informado"

        if isinstance(
            value,
            datetime,
        ):
            return value.strftime(
                "%d/%m/%Y às %H:%M:%S"
            )

        return str(value)
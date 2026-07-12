from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult


class AnalyzedFileCard(QFrame):
    """
    Card responsável por apresentar as informações gerais
    do arquivo atualmente analisado.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("AnalyzedFileCard")

        self.current_result: AnalysisResult | None = None
        self.available_hashes: dict[str, str] = {}

        self._build_ui()
        self._connect_signals()
        self.clear()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 18, 18, 18)
        main_layout.setSpacing(14)

        title_label = QLabel("Arquivo analisado")
        title_label.setObjectName("AnalyzedFileCardTitle")

        self.file_name_label = QLabel("Nenhum arquivo selecionado")
        self.file_name_label.setObjectName("AnalyzedFileName")
        self.file_name_label.setWordWrap(True)
        self.file_name_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        main_layout.addWidget(title_label)
        main_layout.addWidget(self.file_name_label)

        main_layout.addWidget(self._create_separator())

        # Informações gerais
        general_info_layout = QVBoxLayout()
        general_info_layout.setContentsMargins(0, 0, 0, 0)
        general_info_layout.setSpacing(10)

        path_field, self.path_value = self._create_info_field(
            "Caminho",
            multiline=True,
        )
        general_info_layout.addWidget(path_field)

        compact_info_container = QWidget()
        compact_info_container.setObjectName("TransparentContainer")

        compact_info_layout = QGridLayout(compact_info_container)
        compact_info_layout.setContentsMargins(0, 0, 0, 0)
        compact_info_layout.setHorizontalSpacing(10)
        compact_info_layout.setVerticalSpacing(0)
        compact_info_layout.setColumnStretch(0, 1)
        compact_info_layout.setColumnStretch(1, 1)

        extension_field, self.extension_value = self._create_info_field(
            "Extensão"
        )
        size_field, self.size_value = self._create_info_field(
            "Tamanho"
        )

        compact_info_layout.addWidget(extension_field, 0, 0)
        compact_info_layout.addWidget(size_field, 0, 1)

        general_info_layout.addWidget(compact_info_container)

        analyzed_at_field, self.analyzed_at_value = (
            self._create_info_field("Analisado em")
        )
        general_info_layout.addWidget(analyzed_at_field)

        main_layout.addLayout(general_info_layout)

        main_layout.addWidget(self._create_separator())

        # Hash
        hash_title = QLabel("Hash do arquivo")
        hash_title.setObjectName("AnalyzedFileSectionTitle")

        self.hash_algorithm_combo = QComboBox()
        self.hash_algorithm_combo.setObjectName("HashAlgorithmCombo")
        self.hash_algorithm_combo.setMinimumHeight(36)

        self.hash_value_label = QLabel("Hash não disponível")
        self.hash_value_label.setObjectName("AnalyzedFileHashValue")
        self.hash_value_label.setWordWrap(True)
        self.hash_value_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )
        self.hash_value_label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )
        self.hash_value_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )
        self.hash_value_label.setMinimumHeight(62)

        self.copy_hash_button = QPushButton("Copiar hash")
        self.copy_hash_button.setObjectName("CopyHashButton")
        self.copy_hash_button.setCursor(Qt.PointingHandCursor)
        self.copy_hash_button.setMinimumHeight(34)
        self.copy_hash_button.setEnabled(False)

        hash_button_row = QHBoxLayout()
        hash_button_row.setContentsMargins(0, 0, 0, 0)
        hash_button_row.setSpacing(8)
        hash_button_row.addWidget(self.copy_hash_button)
        hash_button_row.addStretch()

        main_layout.addWidget(hash_title)
        main_layout.addWidget(self.hash_algorithm_combo)
        main_layout.addWidget(self.hash_value_label)
        main_layout.addLayout(hash_button_row)

        main_layout.addWidget(self._create_separator())

        # Contexto técnico
        technical_title = QLabel("Contexto técnico")
        technical_title.setObjectName("AnalyzedFileSectionTitle")

        main_layout.addWidget(technical_title)

        producer_field, self.producer_value = self._create_info_field(
            "Producer",
            multiline=True,
        )
        creator_field, self.creator_value = self._create_info_field(
            "Creator",
            multiline=True,
        )
        signature_field, self.signature_value = self._create_info_field(
            "Assinatura digital",
            multiline=True,
        )
        signer_field, self.signer_value = self._create_info_field(
            "Signatário",
            multiline=True,
        )

        main_layout.addWidget(producer_field)
        main_layout.addWidget(creator_field)
        main_layout.addWidget(signature_field)
        main_layout.addWidget(signer_field)

    def _connect_signals(self) -> None:
        self.hash_algorithm_combo.currentTextChanged.connect(
            self._update_selected_hash
        )
        self.copy_hash_button.clicked.connect(self._copy_hash)

    def _create_info_field(
        self,
        title: str,
        multiline: bool = False,
    ) -> tuple[QWidget, QLabel]:
        container = QWidget()
        container.setObjectName("AnalyzedFileField")

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title_label = QLabel(title)
        title_label.setObjectName("AnalyzedFileFieldTitle")

        value_label = QLabel("Não informado")
        value_label.setObjectName("AnalyzedFileFieldValue")
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        value_label.setSizePolicy(
            QSizePolicy.Expanding,
            QSizePolicy.Minimum,
        )

        if multiline:
            value_label.setWordWrap(True)
            value_label.setMinimumHeight(42)
        else:
            value_label.setMinimumHeight(36)

        layout.addWidget(title_label)
        layout.addWidget(value_label)

        return container, value_label

    @staticmethod
    def _create_separator() -> QFrame:
        separator = QFrame()
        separator.setObjectName("AnalyzedFileSeparator")
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Plain)
        return separator

    def update_analysis(
        self,
        result: AnalysisResult | None,
    ) -> None:
        """
        Atualiza todas as informações do card.
        """

        if result is None:
            self.clear()
            return

        self.current_result = result

        file_info = getattr(result, "file_info", None)

        file_name = self._first_value(
            getattr(file_info, "name", None),
            "Arquivo sem nome",
        )

        file_path = self._first_value(
            getattr(file_info, "path", None),
            "Não informado",
        )

        extension = self._first_value(
            getattr(file_info, "extension", None),
            self._extract_extension(file_path),
            "Não informado",
        )

        size = self._first_value(
            getattr(file_info, "size", None),
            getattr(file_info, "size_bytes", None),
        )

        analyzed_at = self._first_value(
            getattr(result, "analyzed_at", None),
            getattr(file_info, "analyzed_at", None),
            getattr(result, "analysis_date", None),
        )

        self.file_name_label.setText(str(file_name))
        self.file_name_label.setToolTip(str(file_name))

        self.path_value.setText(str(file_path))
        self.path_value.setToolTip(str(file_path))

        self.extension_value.setText(
            self._format_extension(extension)
        )
        self.size_value.setText(
            self._format_file_size(size)
        )
        self.analyzed_at_value.setText(
            self._format_datetime(analyzed_at)
        )

        self._update_hashes(result)
        self._update_metadata(result)
        self._update_signature(result)

    def _update_hashes(self, result: AnalysisResult) -> None:
        self.available_hashes.clear()
        self.hash_algorithm_combo.blockSignals(True)
        self.hash_algorithm_combo.clear()

        hash_result = getattr(result, "hash_result", None)

        if hash_result is None:
            hash_result = getattr(result, "hashes", None)

        possible_hashes = {
            "MD5": self._read_attribute(
                hash_result,
                "md5",
                "md5_hash",
            ),
            "SHA-1": self._read_attribute(
                hash_result,
                "sha1",
                "sha_1",
                "sha1_hash",
            ),
            "SHA-224": self._read_attribute(
                hash_result,
                "sha224",
                "sha_224",
                "sha224_hash",
            ),
            "SHA-256": self._read_attribute(
                hash_result,
                "sha256",
                "sha_256",
                "sha256_hash",
            ),
            "SHA-384": self._read_attribute(
                hash_result,
                "sha384",
                "sha_384",
                "sha384_hash",
            ),
            "SHA-512": self._read_attribute(
                hash_result,
                "sha512",
                "sha_512",
                "sha512_hash",
            ),
        }

        for algorithm, hash_value in possible_hashes.items():
            if hash_value:
                self.available_hashes[algorithm] = str(hash_value)
                self.hash_algorithm_combo.addItem(algorithm)

        self.hash_algorithm_combo.blockSignals(False)

        if not self.available_hashes:
            self.hash_value_label.setText("Hash não disponível")
            self.copy_hash_button.setEnabled(False)
            return

        preferred_algorithm = "SHA-256"

        preferred_index = self.hash_algorithm_combo.findText(
            preferred_algorithm
        )

        if preferred_index >= 0:
            self.hash_algorithm_combo.setCurrentIndex(
                preferred_index
            )
        else:
            self.hash_algorithm_combo.setCurrentIndex(0)

        self._update_selected_hash(
            self.hash_algorithm_combo.currentText()
        )

    def _update_metadata(self, result: AnalysisResult) -> None:
        metadata_result = getattr(result, "metadata_result", None)

        if metadata_result is None:
            metadata_result = getattr(result, "metadata", None)

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

        metadata_dict = self._read_attribute(
            metadata_result,
            "metadata",
            "raw",
            "raw_metadata",
        )

        if isinstance(metadata_dict, dict):
            producer = producer or self._find_dict_value(
                metadata_dict,
                "Producer",
                "PDF:Producer",
            )

            creator = creator or self._find_dict_value(
                metadata_dict,
                "Creator",
                "PDF:Creator",
            )

        self.producer_value.setText(
            str(producer) if producer else "Não informado"
        )
        self.producer_value.setToolTip(
            str(producer) if producer else ""
        )

        self.creator_value.setText(
            str(creator) if creator else "Não informado"
        )
        self.creator_value.setToolTip(
            str(creator) if creator else ""
        )

    def _update_signature(self, result: AnalysisResult) -> None:
        signature_result = getattr(
            result,
            "digital_signature_result",
            None,
        )

        if signature_result is None:
            signature_result = getattr(
                result,
                "signature_result",
                None,
            )

        if signature_result is None:
            signature_result = getattr(
                result,
                "digital_signature",
                None,
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

        if isinstance(signatures, list) and signatures:
            first_signature = signatures[0]

            signer = signer or self._read_attribute(
                first_signature,
                "signer",
                "signer_name",
                "subject",
                "certificate_subject",
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
                signature_text = "Assinatura identificada e válida"
            elif is_valid is False:
                signature_text = (
                    "Assinatura identificada, mas não validada"
                )
            else:
                signature_text = "Assinatura identificada"
        elif has_signature is False:
            signature_text = "Nenhuma assinatura digital identificada"
        else:
            signature_text = "Não foi possível determinar"

        self.signature_value.setText(signature_text)

        self.signer_value.setText(
            str(signer) if signer else "Não informado"
        )
        self.signer_value.setToolTip(
            str(signer) if signer else ""
        )

    def _update_selected_hash(self, algorithm: str) -> None:
        hash_value = self.available_hashes.get(algorithm)

        if not hash_value:
            self.hash_value_label.setText("Hash não disponível")
            self.copy_hash_button.setEnabled(False)
            return

        self.hash_value_label.setText(hash_value)
        self.hash_value_label.setToolTip(hash_value)
        self.copy_hash_button.setEnabled(True)

    def _copy_hash(self) -> None:
        algorithm = self.hash_algorithm_combo.currentText()
        hash_value = self.available_hashes.get(algorithm)

        if not hash_value:
            return

        clipboard = QGuiApplication.clipboard()
        clipboard.setText(hash_value)

        original_text = self.copy_hash_button.text()
        self.copy_hash_button.setText("Copiado")

        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            1200,
            lambda: self.copy_hash_button.setText(original_text),
        )

    def clear(self) -> None:
        self.current_result = None
        self.available_hashes.clear()

        self.file_name_label.setText("Nenhum arquivo selecionado")
        self.file_name_label.setToolTip("")

        self.path_value.setText("Não informado")
        self.extension_value.setText("Não informado")
        self.size_value.setText("Não informado")
        self.analyzed_at_value.setText("Não informado")

        self.hash_algorithm_combo.blockSignals(True)
        self.hash_algorithm_combo.clear()
        self.hash_algorithm_combo.blockSignals(False)

        self.hash_value_label.setText("Hash não disponível")
        self.hash_value_label.setToolTip("")
        self.copy_hash_button.setEnabled(False)

        self.producer_value.setText("Não informado")
        self.creator_value.setText("Não informado")
        self.signature_value.setText("Não foi possível determinar")
        self.signer_value.setText("Não informado")

    @staticmethod
    def _read_attribute(
        source: Any,
        *attribute_names: str,
    ) -> Any:
        if source is None:
            return None

        if isinstance(source, dict):
            for name in attribute_names:
                value = source.get(name)

                if value not in (None, ""):
                    return value

            return None

        for name in attribute_names:
            value = getattr(source, name, None)

            if value not in (None, ""):
                return value

        return None

    @staticmethod
    def _find_dict_value(
        values: dict[str, Any],
        *keys: str,
    ) -> Any:
        normalized_values = {
            str(key).lower(): value
            for key, value in values.items()
        }

        for key in keys:
            value = normalized_values.get(key.lower())

            if value not in (None, ""):
                return value

        return None

    @staticmethod
    def _first_value(*values: Any) -> Any:
        for value in values:
            if value not in (None, ""):
                return value

        return None

    @staticmethod
    def _extract_extension(path: Any) -> str | None:
        if not path:
            return None

        suffix = Path(str(path)).suffix

        if not suffix:
            return None

        return suffix

    @staticmethod
    def _format_extension(extension: Any) -> str:
        if not extension:
            return "Não informado"

        text = str(extension).strip()

        if text.startswith("."):
            text = text[1:]

        return text.upper() or "Não informado"

    @staticmethod
    def _format_file_size(size: Any) -> str:
        if size in (None, ""):
            return "Não informado"

        try:
            size_bytes = int(size)
        except (TypeError, ValueError):
            return str(size)

        units = ["B", "KB", "MB", "GB", "TB"]
        value = float(size_bytes)

        for unit in units:
            if value < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(value)} {unit}"

                return f"{value:.2f} {unit}"

            value /= 1024

        return f"{size_bytes} B"

    @staticmethod
    def _format_datetime(value: Any) -> str:
        if value in (None, ""):
            return "Não informado"

        if isinstance(value, datetime):
            return value.strftime("%d/%m/%Y às %H:%M:%S")

        return str(value)
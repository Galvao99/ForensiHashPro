from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult


class FileInvestigationPanel(QFrame):
    """
    Painel lateral com informações do arquivo atualmente selecionado.
    """

    HASH_NAMES = {
        "MD5": "md5",
        "SHA-1": "sha1",
        "SHA-224": "sha224",
        "SHA-256": "sha256",
        "SHA-384": "sha384",
        "SHA-512": "sha512",
    }

    PRODUCER_KEYS = (
        "Producer",
        "PDF:Producer",
        "XMP:Producer",
    )

    CREATOR_KEYS = (
        "Creator",
        "PDF:Creator",
        "XMP:CreatorTool",
        "CreatorTool",
        "Software",
    )

    def __init__(self) -> None:
        super().__init__()

        self.current_result: AnalysisResult | None = None

        self.setObjectName("FileInvestigationPanel")
        self.setMinimumWidth(330)
        self.setMaximumWidth(430)

        self._build_ui()
        self.clear()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        title = QLabel("Arquivo analisado")
        title.setObjectName("InspectorTitle")

        self.file_name_label = QLabel()
        self.file_name_label.setObjectName("InspectorFileName")
        self.file_name_label.setWordWrap(True)
        self.file_name_label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        layout.addWidget(title)
        layout.addWidget(self.file_name_label)

        layout.addWidget(self._separator())

        self.path_value = self._create_value_label()
        self.extension_value = self._create_value_label()
        self.size_value = self._create_value_label()
        self.analyzed_at_value = self._create_value_label()

        layout.addWidget(
            self._build_information_block(
                "Caminho",
                self.path_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Extensão",
                self.extension_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Tamanho",
                self.size_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Analisado em",
                self.analyzed_at_value,
            )
        )

        layout.addWidget(self._separator())

        hash_title = QLabel("Hash do arquivo")
        hash_title.setObjectName("InspectorSectionTitle")

        self.hash_combo = QComboBox()
        self.hash_combo.setObjectName("InspectorHashCombo")
        self.hash_combo.addItems(
            list(self.HASH_NAMES.keys())
        )
        self.hash_combo.setCurrentText("SHA-256")
        self.hash_combo.currentTextChanged.connect(
            self._update_hash_value
        )

        self.hash_value = QLabel()
        self.hash_value.setObjectName("InspectorHashValue")
        self.hash_value.setWordWrap(True)
        self.hash_value.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        self.copy_hash_button = QPushButton("Copiar hash")
        self.copy_hash_button.setObjectName("InspectorCopyButton")
        self.copy_hash_button.clicked.connect(
            self._copy_hash
        )

        layout.addWidget(hash_title)
        layout.addWidget(self.hash_combo)
        layout.addWidget(self.hash_value)
        layout.addWidget(
            self.copy_hash_button,
            alignment=Qt.AlignLeft,
        )

        layout.addWidget(self._separator())

        metadata_title = QLabel("Contexto técnico")
        metadata_title.setObjectName("InspectorSectionTitle")

        self.producer_value = self._create_value_label()
        self.creator_value = self._create_value_label()
        self.signature_value = self._create_value_label()
        self.signer_value = self._create_value_label()

        layout.addWidget(metadata_title)

        layout.addWidget(
            self._build_information_block(
                "Producer",
                self.producer_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Creator",
                self.creator_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Assinatura digital",
                self.signature_value,
            )
        )
        layout.addWidget(
            self._build_information_block(
                "Signatário",
                self.signer_value,
            )
        )

        layout.addStretch()

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        self.current_result = result

        file_info = result.file_info

        self.file_name_label.setText(
            file_info.name
        )

        self.path_value.setText(
            str(file_info.path)
        )

        self.extension_value.setText(
            file_info.extension or "Não identificada"
        )

        self.size_value.setText(
            self._format_size(file_info.size_bytes)
        )

        self.analyzed_at_value.setText(
            result.analyzed_at.strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )

        metadata = self._metadata_values(result)

        producer = self._find_metadata_value(
            metadata,
            self.PRODUCER_KEYS,
        )

        creator = self._find_metadata_value(
            metadata,
            self.CREATOR_KEYS,
        )

        self.producer_value.setText(
            producer or "Não identificado"
        )

        self.creator_value.setText(
            creator or "Não identificado"
        )

        self._update_signature(result)
        self._update_hash_value()

    def clear(self) -> None:
        self.current_result = None

        self.file_name_label.setText(
            "Nenhum arquivo selecionado"
        )
        self.path_value.setText("—")
        self.extension_value.setText("—")
        self.size_value.setText("—")
        self.analyzed_at_value.setText("—")
        self.hash_value.setText("—")
        self.producer_value.setText("—")
        self.creator_value.setText("—")
        self.signature_value.setText("—")
        self.signer_value.setText("—")

        self.copy_hash_button.setEnabled(False)
        self.hash_combo.setEnabled(False)

    def _update_hash_value(self) -> None:
        if self.current_result is None:
            self.hash_value.setText("—")
            return

        selected_algorithm = (
            self.hash_combo.currentText()
        )

        attribute = self.HASH_NAMES.get(
            selected_algorithm
        )

        if not attribute:
            self.hash_value.setText(
                "Hash não identificado"
            )
            return

        value = getattr(
            self.current_result.hashes,
            attribute,
            "",
        )

        self.hash_value.setText(
            value or "Hash não calculado"
        )

        self.copy_hash_button.setEnabled(
            bool(value)
        )
        self.hash_combo.setEnabled(True)

    def _copy_hash(self) -> None:
        hash_text = self.hash_value.text().strip()

        if not hash_text or hash_text in {
            "—",
            "Hash não calculado",
            "Hash não identificado",
        }:
            return

        QApplication.clipboard().setText(
            hash_text
        )

        self.copy_hash_button.setText(
            "Hash copiado"
        )

    def _update_signature(
        self,
        result: AnalysisResult,
    ) -> None:
        signature = result.digital_signature

        if signature.has_signature:
            count = signature.signature_count

            self.signature_value.setText(
                f"Presente • {count} assinatura(s)"
            )
        else:
            self.signature_value.setText(
                "Não identificada"
            )

        self.signer_value.setText(
            signature.signer
            or "Não identificado"
        )

    def _metadata_values(
        self,
        result: AnalysisResult,
    ) -> dict[str, Any]:
        metadata = getattr(
            result,
            "metadata",
            None,
        )

        if metadata is None:
            return {}

        raw = getattr(
            metadata,
            "raw",
            None,
        )

        if isinstance(raw, dict):
            return raw

        return {}

    def _find_metadata_value(
        self,
        metadata: dict[str, Any],
        keys: tuple[str, ...],
    ) -> str:
        for key in keys:
            value = metadata.get(key)

            if value is None:
                continue

            normalized = str(value).strip()

            if normalized:
                return normalized

        return ""

    def _build_information_block(
        self,
        title: str,
        value_widget: QLabel,
    ) -> QWidget:
        container = QWidget()

        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        title_label = QLabel(title)
        title_label.setObjectName(
            "InspectorFieldTitle"
        )

        layout.addWidget(title_label)
        layout.addWidget(value_widget)

        return container

    def _create_value_label(self) -> QLabel:
        label = QLabel()

        label.setObjectName(
            "InspectorFieldValue"
        )

        label.setWordWrap(True)

        label.setTextInteractionFlags(
            Qt.TextSelectableByMouse
        )

        label.setMinimumHeight(30)

        label.setAlignment(
            Qt.AlignLeft | Qt.AlignVCenter
        )

        return label

    def _separator(self) -> QFrame:
        separator = QFrame()
        separator.setObjectName(
            "InspectorSeparator"
        )
        separator.setFrameShape(
            QFrame.HLine
        )

        return separator

    @staticmethod
    def _format_size(
        size_bytes: int,
    ) -> str:
        size = float(size_bytes)

        units = (
            "B",
            "KB",
            "MB",
            "GB",
            "TB",
        )

        for unit in units:
            if size < 1024 or unit == units[-1]:
                if unit == "B":
                    return f"{int(size)} {unit}"

                return f"{size:.2f} {unit}"

            size /= 1024

        return f"{size_bytes} B"
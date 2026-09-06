from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import QUrl, Qt, QThreadPool, Signal
from PySide6.QtGui import QDesktopServices, QFontDatabase, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFileDialog, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QSizePolicy, QVBoxLayout, QWidget,
)

from app.models import AnalysisResult
from app.models.extracted_artifact import ExtractedArtifact
from app.services.byte_range_extraction_service import ByteRangeError, ByteRangeExtractionService
from app.ui.theme import ThemeTokens, theme_tokens
from app.widgets.binary_inspector.hex_grid import HexGridWidget
from app.widgets.deep_file_explorer.tasks import ExplorerTask


class MagicNumberPage(QWidget):
    """Magic-number summary and read-only byte-range inspection workspace."""

    artifact_extracted = Signal(object)
    analyze_artifact_requested = Signal(str)

    INITIAL_HEX_BYTES = 64 * 1024
    MAXIMUM_HEX_BYTES = 2 * 1024 * 1024
    LARGE_EXTRACTION_BYTES = 64 * 1024 * 1024

    def __init__(self, extraction_service: ByteRangeExtractionService | None = None) -> None:
        super().__init__()
        self.extraction_service = extraction_service or ByteRangeExtractionService()
        self.thread_pool = QThreadPool.globalInstance()
        self._tasks: set[ExplorerTask] = set()
        self._result: AnalysisResult | None = None
        self._source_path: Path | None = None
        self._file_size = 0
        self._generation = 0
        self._offset_history: list[int] = []
        self._history_index = -1
        self._syncing_selection = False
        self.last_artifact: ExtractedArtifact | None = None

        self.title = QLabel("Binary Inspector")
        self.title.setObjectName("SectionTitle")
        self.detected_type = QLabel("—")
        self.detected_type.setObjectName("MagicDetectedType")
        self.mime = QLabel("application/octet-stream")
        self.mime.setObjectName("SectionSubtitle")
        self.source_badge = QLabel("SOURCE · MAGIC BYTES")
        self.source_badge.setObjectName("TechnicalBadge")

        self.signature_value = self._mono_value("—")
        self.file_value = self._mono_value("—")
        self.file_value.setObjectName("CurrentFileName")
        self.file_meta_value = QLabel("—")
        self.file_meta_value.setObjectName("CurrentFileMeta")
        self.extension_value = self._mono_value("—")
        self.match_value = QLabel("—")
        self.source_hash_value = self._mono_value("—")

        header = QFrame(); header.setObjectName("MagicCompactHeader")
        header_layout = QVBoxLayout(header); header_layout.setContentsMargins(10, 6, 10, 6); header_layout.setSpacing(2)
        top = QHBoxLayout(); top.addWidget(self.title); top.addSpacing(16); top.addWidget(self.file_value, 1); top.addWidget(self.source_badge)
        file_line = QHBoxLayout(); file_line.addWidget(self.file_meta_value)
        file_line.addWidget(self.detected_type)
        file_line.addWidget(self.mime); file_line.addWidget(self.extension_value); file_line.addStretch()
        technical_line = QHBoxLayout()
        self.signature_caption = QLabel("ASSINATURA")
        technical_line.addWidget(self.signature_caption); technical_line.addWidget(self.signature_value)
        technical_line.addSpacing(12); technical_line.addWidget(self.match_value); technical_line.addStretch()
        self.source_hash_caption = QLabel("SHA-256")
        technical_line.addWidget(self.source_hash_caption); technical_line.addWidget(self.source_hash_value, 1)
        self.copy_source_hash_button = QPushButton("Copiar"); technical_line.addWidget(self.copy_source_hash_button)
        header_layout.addLayout(top); header_layout.addLayout(file_line); header_layout.addLayout(technical_line)

        hex_section = QFrame(); hex_section.setObjectName("HexWorkspace")
        self.compact_header = header
        self.hex_workspace = hex_section
        hex_layout = QVBoxLayout(hex_section); hex_layout.setContentsMargins(0, 0, 0, 0); hex_layout.setSpacing(3)
        self.hex_viewer = HexGridWidget()
        self.hex_grid = self.hex_viewer
        self.hex_viewer.window_requested.connect(self._request_hex_window)
        self.hex_viewer.selection_changed.connect(self._grid_selection_changed)
        self.hex_viewer.cursor_changed.connect(self._grid_cursor_changed)
        self.hex_viewer.copy_hex_requested.connect(self.copy_selected_bytes)
        self.hex_viewer.copy_ascii_requested.connect(self.copy_selected_ascii)
        self.hex_viewer.detect_requested.connect(self.detect_selection_type)
        self.hex_viewer.hash_requested.connect(self.calculate_selection_hash)
        self.hex_viewer.extract_requested.connect(self.extract_selection)
        hex_toolbar_frame = QFrame(); hex_toolbar_frame.setObjectName("HexToolbar")
        hex_toolbar = QHBoxLayout(hex_toolbar_frame); hex_toolbar.setContentsMargins(8, 3, 8, 3)
        hex_label = QLabel("HEX"); hex_label.setObjectName("TechnicalCaption")
        self.goto_input = QLineEdit(); self.goto_input.setPlaceholderText("0x00000000")
        self.goto_input.setMinimumWidth(96); self.goto_input.setMaximumWidth(160)
        self.goto_input.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.goto_button = QPushButton("Ir")
        self.back_button = QPushButton("Anterior"); self.forward_button = QPushButton("Próximo")
        self.back_button.setToolTip("Voltar ao offset anterior")
        self.forward_button.setToolTip("Avançar ao próximo offset do histórico")
        self.goto_caption = QLabel("Ir para offset")
        hex_toolbar.addWidget(hex_label); hex_toolbar.addStretch(); hex_toolbar.addWidget(self.goto_caption)
        hex_toolbar.addWidget(self.goto_input); hex_toolbar.addWidget(self.goto_button)
        hex_toolbar.addWidget(self.back_button); hex_toolbar.addWidget(self.forward_button)
        hex_layout.addWidget(hex_toolbar_frame)
        grid_row = QHBoxLayout(); grid_row.setContentsMargins(0, 0, 0, 0); grid_row.setSpacing(0)
        grid_row.addWidget(self.hex_viewer, 1)
        self.byte_inspector = QFrame(); self.byte_inspector.setObjectName("ByteInspector")
        self.byte_inspector.setMinimumWidth(136); self.byte_inspector.setMaximumWidth(168)
        inspector_layout = QVBoxLayout(self.byte_inspector); inspector_layout.setContentsMargins(8, 8, 8, 8)
        inspector_layout.setSpacing(2)
        inspector_title = QLabel("BYTE INSPECTOR"); inspector_title.setObjectName("TechnicalCaption")
        self.byte_offset_value = self._mono_value("—")
        self.byte_hex_value = self._mono_value("—")
        self.byte_decimal_value = self._mono_value("—")
        self.byte_binary_value = self._mono_value("—")
        self.byte_ascii_value = self._mono_value("—")
        for value in (self.byte_offset_value, self.byte_hex_value, self.byte_decimal_value,
                      self.byte_binary_value, self.byte_ascii_value):
            value.setObjectName("InspectorValue")
        inspector_layout.addWidget(inspector_title)
        for caption, value in (("Offset", self.byte_offset_value), ("Hex", self.byte_hex_value),
                               ("Decimal", self.byte_decimal_value), ("Binary", self.byte_binary_value),
                               ("ASCII", self.byte_ascii_value)):
            label = QLabel(caption); label.setObjectName("InspectorCaption")
            inspector_layout.addWidget(label); inspector_layout.addWidget(value)
        inspector_layout.addStretch()
        grid_row.addWidget(self.byte_inspector)
        hex_layout.addLayout(grid_row, 1)

        selection = QFrame(); selection.setObjectName("SelectionBar")
        self.selection_bar = selection
        selection_layout = QGridLayout(selection); selection_layout.setContentsMargins(8, 5, 8, 5)
        selection_layout.setHorizontalSpacing(6); selection_layout.setVerticalSpacing(4)
        selection_title = QLabel("SELECTION"); selection_title.setObjectName("TechnicalCaption")
        self.selection_title = selection_title
        self.start_input = QLineEdit(); self.start_input.setPlaceholderText("0x00000000")
        self.end_input = QLineEdit(); self.end_input.setPlaceholderText("0x000000FF")
        self.start_input.setMinimumWidth(88); self.start_input.setMaximumWidth(128)
        self.end_input.setMinimumWidth(88); self.end_input.setMaximumWidth(128)
        self.start_input.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.end_input.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.range_status = QLabel("Selecione um intervalo para habilitar as ações.")
        self.range_status.setObjectName("SectionSubtitle")

        self.extract_button = QPushButton("Extrair")
        self.hash_button = QPushButton("SHA-256")
        self.detect_button = QPushButton("Detectar")
        self.extract_button.setObjectName("PrimaryButton")
        self.sidecar_checkbox = QCheckBox("Sidecar JSON")
        self.sidecar_checkbox.setToolTip("Gera o arquivo JSON de proveniência junto ao artefato extraído.")
        self.feedback = QLabel("Arquivo ainda não carregado."); self.feedback.setWordWrap(False)
        self.feedback.setMaximumWidth(230)
        self.feedback.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.feedback.setObjectName("MagicFeedback")
        self.open_folder_button = QPushButton("Abrir pasta")
        self.analyze_button = QPushButton("Analisar no ForensiHash")
        self.open_folder_button.hide(); self.analyze_button.hide()
        selection_layout.addWidget(selection_title, 0, 0)
        selection_layout.addWidget(QLabel("Início"), 0, 1); selection_layout.addWidget(self.start_input, 0, 2)
        selection_layout.addWidget(QLabel("Fim"), 0, 3); selection_layout.addWidget(self.end_input, 0, 4)
        selection_layout.addWidget(self.range_status, 0, 5, 1, 4)
        selection_layout.addWidget(self.detect_button, 1, 2); selection_layout.addWidget(self.hash_button, 1, 3)
        selection_layout.addWidget(self.extract_button, 1, 4); selection_layout.addWidget(self.sidecar_checkbox, 1, 5)
        selection_layout.addWidget(self.open_folder_button, 1, 6)
        selection_layout.setColumnStretch(5, 1)

        status_bar = QFrame(); status_bar.setObjectName("BinaryStatusBar")
        self.status_bar = status_bar
        status_layout = QHBoxLayout(status_bar); status_layout.setContentsMargins(8, 3, 8, 3)
        self.offset_status = QLabel("Offset: 0x00000000")
        self.selection_status = QLabel("Selection: none")
        self.file_size_status = QLabel("File size: —")
        self.loaded_status = QLabel("Loaded: —")
        self.position_status = QLabel("Position: 0.0%")
        status_layout.addWidget(self.offset_status); status_layout.addWidget(self.selection_status)
        status_layout.addWidget(self.file_size_status); status_layout.addWidget(self.loaded_status)
        status_layout.addWidget(self.position_status)
        status_layout.addStretch(); status_layout.addWidget(self.feedback)

        for status_label in (self.offset_status, self.selection_status, self.file_size_status,
                             self.loaded_status, self.position_status):
            status_label.setMinimumWidth(0)
            status_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        for flexible_label in (self.file_value, self.match_value, self.source_hash_value,
                               self.range_status, self.feedback):
            flexible_label.setMinimumWidth(0)
            flexible_label.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)

        layout = QVBoxLayout(self); layout.setContentsMargins(8, 6, 8, 6); layout.setSpacing(5)
        layout.addWidget(header); layout.addWidget(hex_section, 1); layout.addWidget(selection); layout.addWidget(status_bar)

        self.start_input.textChanged.connect(self._validate_selection)
        self.end_input.textChanged.connect(self._validate_selection)
        self.hash_button.clicked.connect(self.calculate_selection_hash)
        self.detect_button.clicked.connect(self.detect_selection_type)
        self.extract_button.clicked.connect(self.extract_selection)
        self.open_folder_button.clicked.connect(self._open_artifact_folder)
        self.analyze_button.clicked.connect(self._request_artifact_analysis)
        self.goto_button.clicked.connect(self.go_to_offset)
        self.goto_input.returnPressed.connect(self.go_to_offset)
        self.back_button.clicked.connect(lambda: self._navigate_history(-1))
        self.forward_button.clicked.connect(lambda: self._navigate_history(1))
        self.copy_source_hash_button.clicked.connect(self._copy_source_hash)
        for button in (self.extract_button, self.hash_button, self.detect_button):
            button.setEnabled(False)
        self.extract_button.setToolTip("Salva os bytes selecionados como uma nova cópia; a origem não é alterada.")
        self.hash_button.setToolTip("Calcula SHA-256 somente sobre a faixa selecionada.")
        self.detect_button.setToolTip("Usa o Magic Number Engine existente sobre a faixa selecionada.")
        self.goto_input.setToolTip("Carrega uma janela limitada iniciada no offset informado.")
        QShortcut(QKeySequence("Ctrl+G"), self, activated=self.goto_input.setFocus)
        QShortcut(QKeySequence("Ctrl+E"), self, activated=self.extract_selection)
        QShortcut(QKeySequence("Ctrl+Shift+C"), self, activated=self.copy_selected_bytes)
        self.setTabOrder(self.goto_input, self.goto_button); self.setTabOrder(self.goto_button, self.hex_viewer)
        self.setTabOrder(self.hex_viewer, self.start_input)
        self.setTabOrder(self.start_input, self.end_input); self.setTabOrder(self.end_input, self.detect_button)
        self.apply_theme(theme_tokens("light"))

    def resizeEvent(self, event) -> None:
        compact = event.size().width() < 900
        narrow = event.size().width() < 760
        self.byte_inspector.setVisible(not narrow)
        self.source_badge.setVisible(not compact)
        self.feedback.setVisible(not compact)
        self.selection_title.setVisible(not compact)
        self.goto_caption.setVisible(not narrow)
        for widget in (self.source_hash_caption, self.source_hash_value,
                       self.copy_source_hash_button, self.match_value):
            widget.setVisible(not narrow)
        for widget in (self.file_size_status, self.loaded_status, self.position_status):
            widget.setVisible(not narrow)
        super().resizeEvent(event)

    @staticmethod
    def _mono_value(text: str) -> QLabel:
        label = QLabel(text); label.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        label.setTextInteractionFlags(Qt.TextSelectableByMouse); label.setWordWrap(True)
        return label

    def update_analysis(self, result: AnalysisResult) -> None:
        self._generation += 1
        self._result = result
        self._source_path = Path(result.file_info.path)
        self._file_size = result.file_info.size_bytes
        self.last_artifact = None
        magic = result.magic_numbers
        self.detected_type.setText(magic.detected_type)
        self.mime.setText(magic.mime_type)
        self.signature_value.setText(magic.signature or "—")
        self.file_value.setText(result.file_info.name)
        self.file_value.setToolTip(result.file_info.name)
        self.file_meta_value.setText(self._format_size(self._file_size))
        self.extension_value.setText(magic.extension or "(sem extensão)")
        self.match_value.setText("Extensão compatível" if magic.extension_matches
                                 else "Extensão não corresponde à assinatura")
        digest = result.hashes.sha256
        self.source_hash_value.setText(f"{digest[:16]}…{digest[-8:]}" if len(digest) > 28 else digest)
        self.source_hash_value.setToolTip(digest)
        self._syncing_selection = True
        self.start_input.clear(); self.end_input.clear(); self.goto_input.clear()
        self._syncing_selection = False
        self._offset_history = [0]; self._history_index = 0
        self.feedback.setText("No selection")
        self.offset_status.setText("Offset: 0x00000000")
        self.file_size_status.setText(f"File size: {self._format_size(self._file_size)}")
        self.loaded_status.setText("Loaded: —")
        self.position_status.setText("Position: 0.0%")
        for value in (self.byte_offset_value, self.byte_hex_value, self.byte_decimal_value,
                      self.byte_binary_value, self.byte_ascii_value): value.setText("—")
        self.open_folder_button.hide(); self.analyze_button.hide()
        self.back_button.setEnabled(False); self.forward_button.setEnabled(False)
        self._validate_selection()
        self.hex_viewer.set_file(self._file_size)

    def _request_hex_window(self, base: int, length: int, request_id: int) -> None:
        if self._source_path is None or self._file_size == 0:
            return
        generation, path = self._generation, self._source_path
        self.hex_viewer.set_loading()
        self._submit(lambda: self.extraction_service.read_range(path, base, length,
                                                                 maximum_bytes=self.MAXIMUM_HEX_BYTES),
                     lambda data: self._hex_loaded(data, base, request_id)
                     if generation == self._generation and path == self._source_path else None,
                     lambda category, message: self._show_hex_error(category, message)
                     if generation == self._generation and path == self._source_path else None)

    def _hex_loaded(self, data: object, base_offset: int, request_id: int) -> None:
        payload = bytes(data)
        self.hex_viewer.accept_window(base_offset, payload, request_id)
        self.loaded_status.setText(
            f"Loaded window: {self._format_size(len(payload))} · cache {self.hex_viewer.cached_window_count}"
        )

    def _show_hex_error(self, category: str, _message: str) -> None:
        safe_messages = {
            "unsupported": "O arquivo de origem não está disponível.",
            "invalid_range": "A faixa solicitada está fora dos limites do arquivo.",
            "limit_exceeded": "A faixa solicitada excede o limite de leitura.",
            "malformed": "A faixa solicitada não pôde ser lida integralmente.",
        }
        self.hex_viewer.set_error(category, safe_messages.get(category, "Não foi possível ler os bytes solicitados."))
        self.feedback.setText("Visualização hexadecimal indisponível")

    def selected_range(self) -> tuple[int, int, int]:
        if self._source_path is None:
            raise ByteRangeError("invalid_range", "Nenhum arquivo está carregado.")
        try:
            start = int(self.start_input.text().strip(), 0)
            end = int(self.end_input.text().strip(), 0)
        except ValueError as error:
            raise ByteRangeError("invalid_range", "Use offsets decimais ou hexadecimais iniciados por 0x.") from error
        length = end - start + 1
        if start < 0 or end < start or end >= self._file_size:
            raise ByteRangeError("invalid_range", "O intervalo deve permanecer dentro do arquivo.")
        return start, end, length

    def _validate_selection(self) -> None:
        try:
            start, end, length = self.selected_range()
            if length > self.extraction_service.max_extract_bytes:
                raise ByteRangeError("limit_exceeded", "A seleção excede o limite de extração configurado.")
        except ByteRangeError as error:
            valid = False
            self.range_status.setText(str(error) if self.start_input.text() or self.end_input.text()
                                      else "Selecione um intervalo para habilitar as ações.")
        else:
            valid = True
            self.range_status.setText(f"{length:,} bytes selecionados · 0x{start:08X}–0x{end:08X}")
        if valid:
            self.selection_status.setText(f"Selection: {length:,} bytes")
            if not self._syncing_selection:
                self._syncing_selection = True
                self.hex_viewer.set_selection(start, end, navigate=True)
                self._syncing_selection = False
        else:
            self.selection_status.setText("Selection: none")
            if not self._syncing_selection and not self.start_input.text() and not self.end_input.text():
                self._syncing_selection = True
                self.hex_viewer.set_selection(None, None)
                self._syncing_selection = False
        self.extract_button.setEnabled(valid)
        bounded_read = valid and length <= self.extraction_service.max_read_bytes
        self.hash_button.setEnabled(bounded_read)
        self.detect_button.setEnabled(bounded_read)

    def _selection_offsets(self) -> tuple[int | None, int | None]:
        try:
            start, end, _ = self.selected_range(); return start, end
        except ByteRangeError:
            return None, None

    def _grid_selection_changed(self, start: object, end: object) -> None:
        if self._syncing_selection:
            return
        self._syncing_selection = True
        self.start_input.setText(f"0x{int(start):08X}" if start is not None else "")
        self.end_input.setText(f"0x{int(end):08X}" if end is not None else "")
        self._syncing_selection = False
        self._validate_selection()

    def _grid_cursor_changed(self, offset: int, byte: object) -> None:
        self.offset_status.setText(f"Offset: 0x{offset:08X}")
        position = (offset / max(self._file_size - 1, 1)) * 100
        self.position_status.setText(f"Position: {position:.1f}%")
        self.byte_offset_value.setText(f"0x{offset:08X}")
        if byte is None:
            for value in (self.byte_hex_value, self.byte_decimal_value,
                          self.byte_binary_value, self.byte_ascii_value): value.setText("…")
            return
        numeric = int(byte)
        self.byte_hex_value.setText(f"{numeric:02X}")
        self.byte_decimal_value.setText(str(numeric))
        self.byte_binary_value.setText(f"{numeric:08b}")
        self.byte_ascii_value.setText(chr(numeric) if 32 <= numeric <= 126 else ".")

    def go_to_offset(self) -> None:
        if self._source_path is None: return
        try:
            offset = int(self.goto_input.text().strip(), 0)
        except ValueError:
            self.feedback.setText("Invalid offset"); return
        if offset < 0 or offset >= self._file_size:
            self.feedback.setText("Offset outside file bounds"); return
        self._record_history(offset)
        self.hex_viewer.go_to_offset(offset)
        self.feedback.setText(f"Positioned at 0x{offset:08X}")

    def _record_history(self, offset: int) -> None:
        if self._history_index >= 0 and self._offset_history[self._history_index] == offset: return
        self._offset_history = self._offset_history[:self._history_index + 1] + [offset]
        self._history_index = len(self._offset_history) - 1
        self._update_history_buttons()

    def _navigate_history(self, delta: int) -> None:
        target = self._history_index + delta
        if not 0 <= target < len(self._offset_history): return
        self._history_index = target; offset = self._offset_history[target]
        self.goto_input.setText(f"0x{offset:08X}")
        self.hex_viewer.go_to_offset(offset)
        self._update_history_buttons()

    def _update_history_buttons(self) -> None:
        self.back_button.setEnabled(self._history_index > 0)
        self.forward_button.setEnabled(0 <= self._history_index < len(self._offset_history) - 1)

    def _copy_source_hash(self) -> None:
        if self._result is not None:
            QApplication.clipboard().setText(self._result.hashes.sha256)
            self.feedback.setText("Source SHA-256 copied")

    def copy_selected_bytes(self) -> None:
        selection = self._selection_or_feedback()
        if selection is None or self._source_path is None: return
        start, _, length = selection
        if length > self.extraction_service.max_read_bytes:
            self.feedback.setText("Selection exceeds copy limit"); return
        self._run_selection("Copying selected bytes...",
                            lambda path: self.extraction_service.read_range(path, start, length),
                            lambda data: self._copy_bytes_completed(bytes(data)))

    def copy_selected_ascii(self) -> None:
        selection = self._selection_or_feedback()
        if selection is None or self._source_path is None: return
        start, _, length = selection
        if length > self.extraction_service.max_read_bytes:
            self.feedback.setText("Selection exceeds copy limit"); return
        self._run_selection("Copying selected ASCII…",
                            lambda path: self.extraction_service.read_range(path, start, length),
                            lambda data: self._copy_ascii_completed(bytes(data)))

    def _copy_ascii_completed(self, data: bytes) -> None:
        QApplication.clipboard().setText("".join(chr(value) if 32 <= value <= 126 else "." for value in data))
        self.feedback.setText(f"Copied {len(data):,} bytes as ASCII")

    def _copy_bytes_completed(self, data: bytes) -> None:
        QApplication.clipboard().setText(data.hex(" ").upper())
        self.feedback.setText(f"Copied {len(data):,} selected bytes")

    @staticmethod
    def _format_size(size: int) -> str:
        if size >= 1024 * 1024: return f"{size / (1024 * 1024):.1f} MiB"
        if size >= 1024: return f"{size / 1024:.1f} KiB"
        return f"{size:,} bytes"

    def calculate_selection_hash(self) -> None:
        selection = self._selection_or_feedback()
        if selection is None: return
        start, _, length = selection
        self._run_selection("Calculando SHA-256 da seleção...",
                            lambda path: self.extraction_service.hash_range(path, start, length),
                            lambda digest: self.feedback.setText(f"SHA-256 da seleção\n{digest}"))

    def detect_selection_type(self) -> None:
        selection = self._selection_or_feedback()
        if selection is None: return
        start, _, length = selection
        self._run_selection("Detectando tipo da seleção...",
                            lambda path: self.extraction_service.detect_range(path, start, length),
                            self._detection_completed)

    def _detection_completed(self, value: object) -> None:
        try:
            _, _, length = self.selected_range()
        except ByteRangeError:
            length = 0
        self.selection_status.setText(f"Selection: {length:,} bytes · {value.detected_format} · {value.mime_type}")
        self.feedback.setText(f"{value.detected_format} signature detected · {value.signature or 'no signature'}")

    def extract_selection(self) -> None:
        selection = self._selection_or_feedback()
        if selection is None or self._source_path is None or self._result is None: return
        start, _, length = selection
        if length > self.LARGE_EXTRACTION_BYTES and not self._confirm_large_extraction(length): return
        destination = self._choose_destination(self._source_path.name)
        if destination is None:
            self.feedback.setText("Extração cancelada; nenhum arquivo foi criado."); return
        source_hash = self._result.hashes.sha256
        self._run_selection("Extraindo seleção para nova cópia...",
                            lambda path: self.extraction_service.extract(
                                path, destination, start, length, source_sha256=source_hash,
                                write_sidecar=self.sidecar_checkbox.isChecked()), self._extraction_completed)

    def _selection_or_feedback(self) -> tuple[int, int, int] | None:
        try: return self.selected_range()
        except ByteRangeError as error:
            self.feedback.setText(f"Intervalo inválido · {error}"); return None

    def _run_selection(self, loading: str, operation: Callable[[Path], object],
                       success: Callable[[object], None]) -> None:
        if self._source_path is None: return
        generation, path = self._generation, self._source_path
        self.feedback.setText(loading)
        self._submit(lambda: operation(path),
                     lambda value: success(value) if generation == self._generation and path == self._source_path else None,
                     lambda category, message: self._show_operation_error(category, message)
                     if generation == self._generation and path == self._source_path else None)

    def _show_operation_error(self, category: str, _message: str) -> None:
        safe_messages = {
            "unsupported": "arquivo de origem indisponível",
            "invalid_range": "faixa fora dos limites do arquivo",
            "limit_exceeded": "faixa acima do limite configurado",
            "malformed": "faixa não pôde ser lida integralmente",
        }
        self.feedback.setText(
            f"Operação indisponível · {safe_messages.get(category, 'erro de leitura')}"
        )

    def _extraction_completed(self, value: object) -> None:
        artifact = value
        self.last_artifact = artifact
        self.feedback.setText(
            f"Artefato extraído com sucesso: {artifact.destination_path.name}\n"
            f"SHA-256: {artifact.extracted_sha256}\nFormato: {artifact.detected_format} · {artifact.detected_mime}"
        )
        self.open_folder_button.show()
        self.artifact_extracted.emit(artifact)

    def _choose_destination(self, source_name: str) -> Path | None:
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar artefato extraído", f"extracted-{source_name}")
        return Path(filename) if filename else None

    def _confirm_large_extraction(self, length: int) -> bool:
        return QMessageBox.question(
            self, "Confirmar extração", f"A seleção possui {length:,} bytes. Deseja criar a nova cópia?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) == QMessageBox.Yes

    def _open_artifact_folder(self) -> None:
        if self.last_artifact: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.last_artifact.destination_path.parent)))

    def _request_artifact_analysis(self) -> None:
        if self.last_artifact: self.analyze_artifact_requested.emit(str(self.last_artifact.destination_path))

    def _submit(self, operation: Callable[[], object], success: Callable[[object], None],
                failure: Callable[[str, str], None]) -> None:
        task = ExplorerTask(operation); self._tasks.add(task)
        task.signals.succeeded.connect(success); task.signals.failed.connect(failure)
        task.signals.finished.connect(lambda task=task: self._tasks.discard(task))
        self.thread_pool.start(task)

    def apply_theme(self, tokens: ThemeTokens) -> None:
        """Apply the active application theme to the custom-painted Hex canvas."""
        self.hex_viewer.set_theme_colors(
            background=tokens.hex_background,
            toolbar_background=tokens.hex_toolbar_background,
            text=tokens.hex_text,
            secondary=tokens.hex_secondary,
            offset=tokens.hex_offset,
            separator=tokens.hex_separator,
            selection=tokens.hex_selection,
            current=tokens.hex_current,
        )

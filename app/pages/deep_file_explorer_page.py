from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QModelIndex, Qt, QThreadPool, Signal
from PySide6.QtGui import QFontDatabase, QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QTabWidget, QTreeView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.deep_structure import DeepFileStructureEngine
from app.models import AnalysisResult
from app.widgets.deep_file_explorer.tasks import ExplorerTask
from app.widgets.deep_file_explorer.hex_viewer import HexViewerWidget
from app.widgets.deep_file_explorer.tree_model import StructureTreeModel, StructureTreeNode


MAX_TEXT_BYTES = 512 * 1024


class DocumentPageViewer(QFrame):
    page_changed = Signal(int)

    def __init__(self, submit: Callable[..., None]) -> None:
        super().__init__()
        self.setObjectName("DeepDocumentViewer")
        self._submit = submit
        self._path: Path | None = None
        self._page = 0
        self._page_count = 0
        self._zoom = 1.0
        self._fit_mode = "page"

        self.previous_button = QPushButton("Anterior")
        self.next_button = QPushButton("Próxima")
        self.page_label = QLabel("Página — / —")
        self.zoom_box = QComboBox()
        self.zoom_box.addItems(["50%", "75%", "100%", "125%", "150%", "200%"])
        self.zoom_box.setCurrentText("100%")
        self.fit_width_button = QPushButton("Ajustar largura")
        self.fit_page_button = QPushButton("Ajustar página")

        toolbar = QHBoxLayout()
        toolbar.addWidget(self.previous_button)
        toolbar.addWidget(self.next_button)
        toolbar.addWidget(self.page_label)
        toolbar.addStretch()
        toolbar.addWidget(self.zoom_box)
        toolbar.addWidget(self.fit_width_button)
        toolbar.addWidget(self.fit_page_button)

        self.image_label = QLabel("Nenhum documento carregado")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(240, 260)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setAlignment(Qt.AlignCenter)
        self.scroll.setWidget(self.image_label)

        layout = QVBoxLayout(self)
        layout.addLayout(toolbar)
        layout.addWidget(self.scroll, 1)

        self.previous_button.clicked.connect(lambda: self.set_page(self._page - 1))
        self.next_button.clicked.connect(lambda: self.set_page(self._page + 1))
        self.zoom_box.currentTextChanged.connect(self._set_zoom)
        self.fit_width_button.clicked.connect(lambda: self._set_fit("width"))
        self.fit_page_button.clicked.connect(lambda: self._set_fit("page"))
        self._update_controls()

    @property
    def page_number(self) -> int:
        return self._page + 1

    def load(self, path: Path) -> None:
        self._path = path
        self._page = 0
        self.image_label.setText("Renderizando página...")
        self._render()

    def clear(self, message: str) -> None:
        self._path = None
        self._page_count = 0
        self.image_label.clear()
        self.image_label.setText(message)
        self._update_controls()

    def show_image(self, data: bytes | QImage, provenance: str = "") -> None:
        self._path = None
        self._page_count = 0
        image = data if isinstance(data, QImage) else QImage.fromData(data)
        if image.isNull():
            size = len(data) if isinstance(data, bytes) else 0
            self.clear(f"Preview binário disponível: {size:,} bytes")
            return
        pixmap = QPixmap.fromImage(image)
        self.image_label.setPixmap(pixmap)
        self.image_label.resize(image.size())
        self.image_label.setToolTip(provenance)
        self._update_controls()

    def set_page(self, page: int) -> None:
        if self._page_count and 0 <= page < self._page_count and page != self._page:
            self._page = page
            self._render()
            self.page_changed.emit(self._page + 1)

    def _set_zoom(self, value: str) -> None:
        self._zoom = int(value.rstrip("%")) / 100
        self._fit_mode = "zoom"
        self._render()

    def _set_fit(self, mode: str) -> None:
        self._fit_mode = mode
        self._render()

    def _render(self) -> None:
        if self._path is None:
            return
        path, page, zoom, fit_mode = self._path, self._page, self._zoom, self._fit_mode
        viewport = self.scroll.viewport().size()

        def operation() -> tuple[bytes, int]:
            import fitz
            document = fitz.open(path)
            try:
                count = len(document)
                selected = document[min(page, max(count - 1, 0))]
                rect = selected.rect
                scale = zoom
                if fit_mode == "width" and rect.width:
                    scale = max(0.1, (viewport.width() - 24) / rect.width)
                elif fit_mode == "page" and rect.width and rect.height:
                    scale = max(0.1, min((viewport.width() - 24) / rect.width, (viewport.height() - 24) / rect.height))
                pixmap = selected.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                return pixmap.tobytes("png"), count
            finally:
                document.close()

        self.image_label.setText("Renderizando página...")
        self._submit(operation, self._rendered, self._render_failed)

    def _rendered(self, result: object) -> None:
        data, count = result
        self._page_count = count
        image = QImage.fromData(data)
        self.image_label.setPixmap(QPixmap.fromImage(image))
        self.image_label.resize(image.size())
        self._update_controls()

    def _render_failed(self, category: str, message: str) -> None:
        self.image_label.setText(f"Página indisponível\nCategoria técnica: {category}\n{message}")

    def _update_controls(self) -> None:
        self.page_label.setText(f"Página {self._page + 1} / {self._page_count}" if self._page_count else "Página — / —")
        self.previous_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page_count > 0 and self._page + 1 < self._page_count)


class ObjectInspector(QTabWidget):
    reference_requested = Signal(str)

    def __init__(self, submit: Callable[..., None]) -> None:
        super().__init__()
        self._submit = submit
        self._session: Any = None
        self._node: StructureTreeNode | None = None
        self._loaded: set[tuple[str, str]] = set()
        self._selection_token = 0

        self.preview_label = QLabel("Selecione um recurso visual.")
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setWordWrap(True)
        preview_scroll = QScrollArea()
        preview_scroll.setWidgetResizable(True)
        preview_scroll.setWidget(self.preview_label)
        self.properties = QTreeWidget()
        self.properties.setHeaderLabels(["Propriedade", "Tipo", "Valor"])
        self.properties.setAlternatingRowColors(True)
        self.decoded = QPlainTextEdit()
        self.decoded.setReadOnly(True)
        self.decoded.setPlaceholderText("Selecione um stream decodificável.")
        self.raw = QPlainTextEdit()
        self.raw.setReadOnly(True)
        self.raw.setPlaceholderText("Selecione um objeto.")
        self.text = QPlainTextEdit()
        self.text.setReadOnly(True)
        self.text.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.text.setFont(QFontDatabase.systemFont(QFontDatabase.FixedFont))
        self.hex_viewer = HexViewerWidget()

        self.addTab(preview_scroll, "Preview")
        self.addTab(self.properties, "Properties")
        self.addTab(self.decoded, "Decoded")
        self.addTab(self.raw, "Raw")
        self.addTab(self.text, "Text")
        self.addTab(self.hex_viewer, "Hex")
        self.currentChanged.connect(self._load_current)
        self.properties.itemDoubleClicked.connect(self._property_activated)

    def set_session(self, session: Any) -> None:
        self._session = session
        self._node = None
        self._selection_token += 1
        self._loaded.clear()
        self.clear_selection()

    def select_node(self, node: StructureTreeNode | None) -> None:
        self._node = node
        self._selection_token += 1
        self._loaded.clear()
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("Selecione a aba para carregar o conteúdo sob demanda.")
        self.decoded.clear()
        self.raw.clear()
        self.text.clear()
        self.hex_viewer.clear()
        capabilities = getattr(node, "capabilities", None) if node is not None else frozenset()
        if capabilities is None:
            capabilities = frozenset({"summary", "preview", "decoded", "raw", "hex"})
        for index, capability in ((0, "preview"), (1, "summary"), (2, "decoded"), (3, "raw"),
                                  (4, "text"), (5, "hex")):
            self.setTabVisible(index, capability in capabilities)
        self.setCurrentIndex(1)
        self._show_properties(node)
        self._load_current()

    def clear_selection(self) -> None:
        self.properties.clear()
        self.preview_label.setText("Selecione um objeto estrutural.")
        self.decoded.clear()
        self.raw.clear()
        self.text.clear()
        self.hex_viewer.clear()

    def _load_current(self) -> None:
        node = self._node
        if self._session is None or node is None:
            return
        tab = self.tabText(self.currentIndex()).lower()
        key = (getattr(node, "id", "") or str(getattr(node, "object_id", id(node))), tab)
        if key in self._loaded:
            return
        self._loaded.add(key)
        if tab == "preview":
            self.preview_label.setText("Gerando preview...")
            operation = self._preview_operation(node)
            if operation: self._submit_current(operation, self._show_preview, self._preview_failed)
        elif tab == "decoded":
            self.decoded.setPlainText("Decodificando stream...")
            operation = self._content_operation(node, "decoded")
            if operation: self._submit_current(operation, lambda data: self.decoded.setPlainText(_display_payload(data)), self._decoded_failed)
        elif tab == "raw":
            self.raw.setPlainText("Carregando representação raw...")
            operation = self._content_operation(node, "raw")
            if operation: self._submit_current(operation, lambda data: self.raw.setPlainText(_display_payload(data)), self._raw_failed)
        elif tab == "text":
            self.text.setPlainText("Carregando texto...")
            operation = self._content_operation(node, "text")
            if operation: self._submit_current(operation, lambda data: self.text.setPlainText(_display_payload(data)), self._text_failed)
        elif tab == "hex":
            self.hex_viewer.set_loading()
            operation = self._content_operation(node, "raw")
            if operation: self._submit_current(operation, self.hex_viewer.set_bytes, self.hex_viewer.set_error)

    def _content_operation(self, node: StructureTreeNode, mode: str) -> Callable[[], object] | None:
        session = self._session
        if node.kind == "jpeg_segment": return lambda: session.get_segment_raw(node.segment_index)
        if node.kind == "jpeg_scan": return lambda: session.get_scan_raw(node.payload["index"])
        if node.kind == "jpeg_trailing": return session.get_trailing_bytes
        if node.kind == "jpeg_xmp":
            return (lambda: session.get_xmp_text(node.payload["id"])) if mode == "text" else (lambda: session.get_xmp_raw(node.payload["id"]))
        if node.kind in {"jpeg_icc_group", "jpeg_icc_chunk_group", "jpeg_icc_chunk"}: return session.get_icc_profile
        if node.kind == "jpeg_asset": return lambda: session.get_visual_asset(node.preview_asset_id)
        if node.kind == "jpeg_comment" and mode == "text": return lambda: node.payload.get("text") or ""
        if node.kind == "jpeg_exif_entry" and mode == "decoded": return lambda: node.payload.get("decoded_value")
        if not node.object_id: return None
        if mode == "text":
            if node.kind == "metadata": return lambda: session.get_metadata_text(node.object_id)
            if node.kind == "embedded": return lambda: session.get_embedded_file(node.object_id)
        if mode == "decoded":
            if node.kind == "embedded": return lambda: session.get_embedded_file(node.object_id)
            if node.kind == "metadata": return lambda: session.get_metadata_text(node.object_id)
            return lambda: session.get_decoded_stream(node.object_id)
        if mode == "raw":
            if node.kind in {"stream", "resource_image", "resource_thumbnail", "resource_form", "resource_mask"}:
                return lambda: session.get_raw_stream(node.object_id)
            return lambda: session.get_raw_object(node.object_id)
        return None

    def _preview_operation(self, node: StructureTreeNode) -> Callable[[], object] | None:
        preview_asset_id = getattr(node, "preview_asset_id", None) or getattr(node, "object_id", None)
        if not preview_asset_id: return None
        session = self._session
        if node.kind == "jpeg_asset":
            return lambda: (QImage.fromData(bytes(session.get_preview(preview_asset_id))),
                            {"source_object_id": preview_asset_id, "provenance": {"transformation": "none"}})
        return lambda: (QImage.fromData(bytes(session.get_preview(preview_asset_id))),
                        session.get_visual_asset(preview_asset_id))

    def _submit_current(self, operation: Callable[[], object], success: Callable[[object], None],
                        failure: Callable[[str, str], None]) -> None:
        token, session = self._selection_token, self._session
        self._submit(operation,
                     lambda value: success(value) if token == self._selection_token and session is self._session else None,
                     lambda category, message: failure(category, message)
                     if token == self._selection_token and session is self._session else None)

    def _show_properties(self, node: StructureTreeNode | None) -> None:
        self.properties.clear()
        if node is None:
            return
        payload = self._summary_payload(node)
        if is_dataclass(payload):
            payload = asdict(payload)
        if node.object_id and self._session is not None and node.kind not in {"properties", "embedded", "metadata", "annotation", "signature"} and not node.kind.startswith("jpeg_"):
            self._submit_current(lambda: self._session.get_object(node.object_id), self._populate_properties,
                         lambda category, message: self._populate_properties({"error": {"category": category, "message": message}}))
        else:
            self._populate_properties(payload or {"kind": node.kind, "object_id": node.object_id})

    @staticmethod
    def _summary_payload(node: StructureTreeNode) -> object:
        payload = asdict(node.payload) if is_dataclass(node.payload) else node.payload
        if isinstance(payload, dict):
            payload = dict(payload)
            payload.setdefault("source", node.kind)
            if getattr(node, "path", None): payload.setdefault("structural_path", node.path)
            if getattr(node, "object_id", None): payload.setdefault("object_id", node.object_id)
            if getattr(node, "segment_index", None) is not None: payload.setdefault("segment_index", node.segment_index)
            if node.kind == "jpeg_exif_entry":
                tag_id = payload.get("tag_id")
                if isinstance(tag_id, int): payload["tag_id_hex"] = f"0x{tag_id:04X}"
                type_id = payload.get("value_type")
                payload["value_type_name"] = {1: "BYTE", 2: "ASCII", 3: "SHORT", 4: "LONG", 5: "RATIONAL",
                                                   6: "SBYTE", 7: "UNDEFINED", 8: "SSHORT", 9: "SLONG",
                                                   10: "SRATIONAL", 11: "FLOAT", 12: "DOUBLE"}.get(type_id, "UNKNOWN")
                if payload.get("raw_value_location") is not None:
                    payload["absolute_offset_hex"] = f"0x{payload['raw_value_location']:08X}"
        return payload

    def _populate_properties(self, value: object) -> None:
        self.properties.clear()
        _append_property_items(self.properties.invisibleRootItem(), value)
        self.properties.expandToDepth(1)
        self.properties.resizeColumnToContents(0)

    def _property_activated(self, item: QTreeWidgetItem, _column: int) -> None:
        reference = item.data(0, Qt.UserRole)
        if reference:
            self.reference_requested.emit(str(reference))

    def _show_preview(self, result: object) -> None:
        data, asset = result
        image = data if isinstance(data, QImage) else QImage.fromData(data)
        if image.isNull():
            size = len(data) if isinstance(data, bytes) else 0
            self.preview_label.setText(f"Preview binário disponível: {size:,} bytes")
            return
        pixmap = QPixmap.fromImage(image)
        self.preview_label.setPixmap(pixmap)
        provenance = asset.get("provenance", {})
        self.preview_label.setToolTip(
            f"Objeto: {asset.get('source_object_id')}\nFiltro: {provenance.get('source_filter') or '—'}\n"
            f"Transformação: {provenance.get('transformation') or 'nenhuma'}\nReconstruído: {'sim' if asset.get('reconstructed') else 'não'}"
        )

    def _preview_failed(self, category: str, message: str) -> None:
        self.preview_label.setText(f"Preview indisponível\nMotivo técnico: {category}\n{message}")

    def _decoded_failed(self, category: str, message: str) -> None:
        self.decoded.setPlainText(f"Stream decodificado indisponível\nCategoria técnica: {category}\n{message}")

    def _raw_failed(self, category: str, message: str) -> None:
        self.raw.setPlainText(f"Representação raw indisponível\nCategoria técnica: {category}\n{message}")

    def _text_failed(self, category: str, message: str) -> None:
        self.text.setPlainText(f"Texto indisponível\nCategoria técnica: {category}\n{message}")


class DeepFileExplorerPage(QWidget):
    def __init__(self, engine: DeepFileStructureEngine | None = None) -> None:
        super().__init__()
        self.engine = engine or DeepFileStructureEngine()
        self.thread_pool = QThreadPool.globalInstance()
        self._tasks: set[ExplorerTask] = set()
        self._result: AnalysisResult | None = None
        self._session: Any = None
        self._loaded_path: Path | None = None
        self._loading_path: Path | None = None
        self._preview_token = 0
        self.tree_model = StructureTreeModel()

        self.title = QLabel("Deep File Explorer")
        self.title.setObjectName("SectionTitle")
        self.file_label = QLabel("Selecione um PDF ou JPEG analisado.")
        self.file_label.setObjectName("SectionSubtitle")
        self.file_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.status_label = QLabel("O explorador opera em modo somente leitura.")
        self.status_label.setWordWrap(True)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar 42 0 R, Im1, XObject, FlateDecode...")
        self.search.setClearButtonEnabled(True)
        self.locate_page_button = QPushButton("Localizar página na estrutura")

        header = QHBoxLayout()
        header.addWidget(self.title)
        header.addWidget(self.file_label, 1)
        header.addWidget(self.search)
        header.addWidget(self.locate_page_button)

        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.document_viewer = DocumentPageViewer(self._submit)
        self.tree = QTreeView()
        self.tree.setModel(self.tree_model)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAlternatingRowColors(True)
        self.inspector = ObjectInspector(self._submit)

        main_splitter = QSplitter(Qt.Horizontal)
        main_splitter.addWidget(self.tree)
        main_splitter.addWidget(self.document_viewer)
        main_splitter.addWidget(self.inspector)
        main_splitter.setStretchFactor(0, 2)
        main_splitter.setStretchFactor(1, 3)
        main_splitter.setStretchFactor(2, 2)
        main_splitter.setSizes([340, 620, 420])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.summary)
        layout.addWidget(self.status_label)
        layout.addWidget(main_splitter, 1)

        self.tree.selectionModel().currentChanged.connect(self._tree_selection_changed)
        self.search.returnPressed.connect(self.find_next)
        self.locate_page_button.clicked.connect(self.locate_current_page)
        self.inspector.reference_requested.connect(self._navigate_object)

    def update_analysis(self, result: AnalysisResult) -> None:
        previous_path = Path(self._result.file_info.path) if self._result else None
        self._result = result
        path = Path(result.file_info.path)
        if previous_path != path:
            self._discard_session()
        sha = getattr(getattr(result, "hashes", None), "sha256", "") or "—"
        self.file_label.setText(f"{result.file_info.name} · {result.file_info.size_bytes:,} bytes · SHA-256: {sha}")
        structure_format = self._structure_format(result, path)
        if structure_format not in {"pdf", "jpeg"}:
            self.status_label.setText("Estrutura profunda indisponível para este formato.")
            self.document_viewer.clear("Visualização estrutural disponível para PDF e JPEG.")
            self._set_model(StructureTreeModel())
            self.inspector.set_session(None)
        elif self.isVisible():
            self.ensure_loaded()
        else:
            self.status_label.setText("Estrutura pronta para ser carregada ao abrir esta página.")

    def ensure_loaded(self) -> None:
        if self._result is None:
            return
        path = Path(self._result.file_info.path)
        structure_format = self._structure_format(self._result, path)
        if structure_format not in {"pdf", "jpeg"} or self._loaded_path == path or self._loading_path == path:
            return
        self.status_label.setText("Carregando estrutura...")
        self._loading_path = path
        if structure_format == "pdf":
            self.document_viewer.load(path)
            operation = lambda: self.engine.analyze_pdf(path)
        else:
            self.document_viewer.clear("JPEG Structural Report disponível. Explorer visual completo será implementado em sprint futura.")
            operation = lambda: self.engine.analyze_jpeg(path)
        self._submit(
            operation,
            lambda session, requested_path=path: self._structure_loaded_for(requested_path, session),
            lambda category, message, requested_path=path: self._structure_failed_for(
                requested_path, category, message,
            ),
        )

    def find_next(self) -> None:
        query = self.search.text().strip().casefold()
        if not query:
            return
        objects_index = self._find_kind_index("objects")
        if objects_index.isValid() and self.tree_model.canFetchMore(objects_index):
            self.tree_model.fetchMore(objects_index)
        indexes = self.tree_model.match(
            self.tree_model.index(0, 0), StructureTreeModel.SearchRole, query, 1,
            Qt.MatchContains | Qt.MatchRecursive | Qt.MatchWrap,
        )
        if indexes:
            self._select_index(indexes[0])
            self.status_label.setText(f"Correspondência localizada para: {self.search.text().strip()}")
        else:
            self.status_label.setText(f"Nenhuma correspondência para: {self.search.text().strip()}")

    def locate_current_page(self) -> None:
        index = self.tree_model.page_index(self.document_viewer.page_number)
        if index.isValid():
            self._select_index(index)

    def _structure_loaded_for(self, path: Path, value: object) -> None:
        if self._result is None or Path(self._result.file_info.path) != path:
            return
        self._loading_path = None
        self._structure_loaded(value)

    def _structure_loaded(self, value: object) -> None:
        session = value
        self._session = session
        self._loaded_path = Path(self._result.file_info.path) if self._result else None
        self._set_model(StructureTreeModel(session.report))
        self.inspector.set_session(session)
        report = session.report
        if report.format.casefold() == "jpeg":
            physical = report.physical_info
            frame = report.frames[0] if report.frames else {}
            dimensions = f"{frame.get('width')}×{frame.get('height')}" if frame else "—"
            self.summary.setText(
                f"JPEG  ·  Segmentos {physical.segment_count}  ·  Scans {physical.scan_count}  ·  "
                f"Dimensões {dimensions}  ·  EXIF {'sim' if report.exif else 'não'}  ·  "
                f"XMP {'sim' if report.xmp else 'não'}  ·  ICC {'sim' if report.icc else 'não'}  ·  "
                f"Trailing bytes {physical.trailing_bytes_length}"
            )
            self.status_label.setText(
                f"JPEG Structural Report disponível. Versão {report.structure_version}. "
                f"Warnings técnicos: {len(report.warnings)}. Árvore JPEG detalhada adiada."
            )
            self.locate_page_button.setEnabled(False)
            root = self.tree_model.index(0, 0)
            self.tree.expand(root)
            self._load_central_preview("jpeg_main", "Source: arquivo JPEG original")
            return
        summary = report.summary
        self.locate_page_button.setEnabled(True)
        self.summary.setText(
            f"PDF {report.physical.pdf_version or '—'}  ·  Objetos {summary.object_count}  ·  Páginas {summary.page_count}  ·  "
            f"Streams {summary.stream_count}  ·  Imagens únicas {summary.unique_image_objects}  ·  Usos de imagem {summary.image_references}  ·  "
            f"Fonts {summary.unique_font_objects}  ·  Forms {len(report.forms)}  ·  Annotations {summary.unique_annotation_objects}  ·  "
            f"Embedded files {summary.embedded_file_count}  ·  Signatures {summary.signature_dictionary_count}  ·  EOF markers {report.physical.eof_count}"
        )
        warning_count = len(report.parser_warnings)
        self.status_label.setText(
            f"Estrutura carregada em modo somente leitura. Warnings técnicos: {warning_count}. "
            "Previews e streams são carregados somente quando solicitados."
        )
        root = self.tree_model.index(0, 0)
        self.tree.expand(root)

    def _structure_failed_for(self, path: Path, category: str, message: str) -> None:
        if self._result is None or Path(self._result.file_info.path) != path:
            return
        self._loading_path = None
        self._structure_failed(category, message)

    def _structure_failed(self, category: str, message: str) -> None:
        self._discard_session()
        format_name = self._structure_format(self._result, Path(self._result.file_info.path)) if self._result else "arquivo"
        self.status_label.setText(
            f"Não foi possível construir a estrutura deste {format_name.upper()}. "
            f"Categoria técnica: {category}. Detalhe: {message}"
        )

    def release_analysis(self) -> None:
        """Release file-bound native sessions when the workspace returns home."""
        self._result = None
        self._discard_session()
        self._set_model(StructureTreeModel())
        self.inspector.set_session(None)
        self.summary.clear()
        self.file_label.setText("Selecione um PDF ou JPEG analisado.")
        self.status_label.setText("O explorador opera em modo somente leitura.")
        self.document_viewer.clear("Nenhum documento carregado")

    def _discard_session(self) -> None:
        self._preview_token += 1
        self._session = None
        self._loaded_path = None
        self._loading_path = None

    @staticmethod
    def _structure_format(result: AnalysisResult | None, path: Path) -> str | None:
        detected = getattr(getattr(result, "magic_numbers", None), "detected_format", None)
        if detected:
            normalized = str(detected).casefold()
            return normalized if normalized in {"pdf", "jpeg"} else None
        suffix = path.suffix.casefold()
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".jpg", ".jpeg"}:
            return "jpeg"
        return None

    def _tree_selection_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        node = self.tree_model.node_from_index(current)
        if node is not None and node.kind == "structural_link" and isinstance(node.payload, dict):
            target = node.payload.get("structural_target_id")
            if target:
                self._navigate_object(f"node:{target}")
                return
        self.inspector.select_node(node)
        self._preview_token += 1
        if node is None:
            return
        if node.kind == "page" and isinstance(node.payload, dict):
            self.document_viewer.set_page(max(int(node.payload.get("page_number", 1)) - 1, 0))
        elif "preview" in node.capabilities and node.preview_asset_id:
            self._load_central_preview(node.preview_asset_id, self._provenance_text(node))
        else:
            self.document_viewer.clear("Este elemento não possui representação visual direta.")

    def _load_central_preview(self, asset_id: str, provenance: str) -> None:
        if self._session is None:
            return
        token, session = self._preview_token, self._session
        self.document_viewer.clear("Carregando preview sob demanda...")
        self._submit(
            lambda: QImage.fromData(bytes(session.get_preview(asset_id))),
            lambda image: self.document_viewer.show_image(image, provenance)
            if token == self._preview_token and session is self._session else None,
            lambda category, message: self.document_viewer.clear(
                f"Preview indisponível\nCategoria técnica: {category}\n{message}"
            ) if token == self._preview_token and session is self._session else None,
        )

    @staticmethod
    def _provenance_text(node: StructureTreeNode) -> str:
        parts = [f"Source: {node.kind}"]
        if node.path:
            parts.append(f"Path: {node.path}")
        if node.object_id:
            parts.append(f"Object: {node.object_id}")
        if node.segment_index is not None:
            parts.append(f"Segment: #{node.segment_index}")
        return "\n".join(parts)

    def _navigate_object(self, object_id: str) -> None:
        if object_id.startswith("node:"):
            index = self.tree_model.index_for_node_id(object_id.removeprefix("node:"))
            if index.isValid(): self._select_index(index)
            return
        indexes = self.tree_model.indexes_for_object(object_id)
        if not indexes:
            objects_index = self._find_kind_index("objects")
            if objects_index.isValid() and self.tree_model.canFetchMore(objects_index):
                self.tree_model.fetchMore(objects_index)
                indexes = self.tree_model.indexes_for_object(object_id)
        if indexes:
            self._select_index(indexes[-1])

    def _set_model(self, model: StructureTreeModel) -> None:
        old = self.tree.selectionModel()
        if old is not None:
            try:
                old.currentChanged.disconnect(self._tree_selection_changed)
            except RuntimeError:
                pass
        self.tree_model = model
        self.tree.setModel(model)
        self.tree.selectionModel().currentChanged.connect(self._tree_selection_changed)

    def _select_index(self, index: QModelIndex) -> None:
        parent = index.parent()
        while parent.isValid():
            self.tree.expand(parent)
            parent = parent.parent()
        self.tree.setCurrentIndex(index)
        self.tree.scrollTo(index)

    def _find_kind_index(self, kind: str) -> QModelIndex:
        def walk(parent: QModelIndex = QModelIndex()) -> QModelIndex:
            for row in range(self.tree_model.rowCount(parent)):
                index = self.tree_model.index(row, 0, parent)
                node = self.tree_model.node_from_index(index)
                if node and node.kind == kind:
                    return index
                result = walk(index)
                if result.isValid():
                    return result
            return QModelIndex()
        return walk()

    def _submit(self, operation: Callable[[], Any], success: Callable[[object], None],
                failure: Callable[[str, str], None]) -> None:
        task = ExplorerTask(operation)
        self._tasks.add(task)
        task.signals.succeeded.connect(success)
        task.signals.failed.connect(failure)
        task.signals.finished.connect(lambda task=task: self._tasks.discard(task))
        self.thread_pool.start(task)


def _append_property_items(parent: QTreeWidgetItem, value: object, key: str = "value") -> None:
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        for item_key, item_value in value.items():
            kind = item_value.get("kind", "dictionary") if isinstance(item_value, dict) else type(item_value).__name__
            item = QTreeWidgetItem([str(item_key), str(kind), _scalar_text(item_value)])
            if isinstance(item_value, dict) and item_value.get("reference"):
                item.setData(0, Qt.UserRole, str(item_value["reference"]))
                item.setToolTip(0, "Duplo clique para navegar até o objeto referenciado")
            if item_key == "structural_target_id" and isinstance(item_value, str):
                item.setData(0, Qt.UserRole, f"node:{item_value}")
                item.setToolTip(0, "Duplo clique para navegar até a estrutura referenciada")
            parent.addChild(item)
            if isinstance(item_value, (dict, list, tuple)):
                _append_property_items(item, item_value, str(item_key))
    elif isinstance(value, (list, tuple)):
        for index, item_value in enumerate(value):
            item = QTreeWidgetItem([f"[{index}]", type(item_value).__name__, _scalar_text(item_value)])
            parent.addChild(item)
            if isinstance(item_value, (dict, list, tuple)):
                _append_property_items(item, item_value, str(index))
    else:
        parent.addChild(QTreeWidgetItem([key, type(value).__name__, str(value)]))


def _scalar_text(value: object) -> str:
    if isinstance(value, dict):
        if value.get("kind") == "reference":
            return str(value.get("value") or value.get("reference") or "reference")
        if "value" in value and len(value) <= 2:
            return str(value["value"])
        return "{…}"
    if isinstance(value, (list, tuple)):
        return f"[{len(value)} itens]"
    if value is None:
        return "null"
    return str(value)


def _display_payload(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    data = bytes(payload)
    truncated = len(data) > MAX_TEXT_BYTES
    visible = data[:MAX_TEXT_BYTES]
    try:
        text = visible.decode("utf-8")
        if sum(char.isprintable() or char in "\r\n\t" for char in text) / max(len(text), 1) > 0.85:
            suffix = f"\n\n[visualização limitada a {MAX_TEXT_BYTES:,} de {len(data):,} bytes]" if truncated else ""
            return text + suffix
    except UnicodeDecodeError:
        pass
    rows = [f"{offset:08X}  " + " ".join(f"{byte:02X}" for byte in visible[offset:offset + 16])
            for offset in range(0, len(visible), 16)]
    header = f"Stream binário — {len(data):,} bytes\n"
    suffix = f"\n[hexadecimal limitado a {MAX_TEXT_BYTES:,} bytes]" if truncated else ""
    return header + "\n".join(rows) + suffix

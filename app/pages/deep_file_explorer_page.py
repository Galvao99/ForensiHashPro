from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QModelIndex, Qt, QThreadPool, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QPlainTextEdit, QPushButton, QScrollArea, QSizePolicy, QSplitter,
    QTabWidget, QTreeView, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)

from app.deep_structure import DeepFileStructureEngine
from app.models import AnalysisResult
from app.widgets.deep_file_explorer.tasks import ExplorerTask
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
    def __init__(self, submit: Callable[..., None]) -> None:
        super().__init__()
        self._submit = submit
        self._session: Any = None
        self._node: StructureTreeNode | None = None
        self._loaded: set[tuple[str, str]] = set()

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

        self.addTab(preview_scroll, "Preview")
        self.addTab(self.properties, "Properties")
        self.addTab(self.decoded, "Decoded")
        self.addTab(self.raw, "Raw")
        self.currentChanged.connect(self._load_current)

    def set_session(self, session: Any) -> None:
        self._session = session
        self._node = None
        self._loaded.clear()
        self.clear_selection()

    def select_node(self, node: StructureTreeNode | None) -> None:
        self._node = node
        self._loaded.clear()
        self.preview_label.setPixmap(QPixmap())
        self.preview_label.setText("Selecione a aba para carregar o conteúdo sob demanda.")
        self.decoded.clear()
        self.raw.clear()
        self._show_properties(node)
        self._load_current()

    def clear_selection(self) -> None:
        self.properties.clear()
        self.preview_label.setText("Selecione um objeto estrutural.")
        self.decoded.clear()
        self.raw.clear()

    def _load_current(self) -> None:
        node = self._node
        if self._session is None or node is None or not node.object_id:
            return
        tab = self.tabText(self.currentIndex()).lower()
        key = (node.object_id, tab)
        if key in self._loaded:
            return
        self._loaded.add(key)
        if tab == "preview":
            self.preview_label.setText("Gerando preview...")
            self._submit(lambda: (self._session.get_preview(node.object_id), self._session.get_visual_asset(node.object_id)),
                         self._show_preview, self._preview_failed)
        elif tab == "decoded":
            self.decoded.setPlainText("Decodificando stream...")
            if node.kind == "metadata":
                operation = lambda: self._session.get_metadata_text(node.object_id)
            elif node.kind == "embedded":
                operation = lambda: self._session.get_embedded_file(node.object_id)
            else:
                operation = lambda: self._session.get_decoded_stream(node.object_id)
            self._submit(operation, lambda data: self.decoded.setPlainText(_display_payload(data)), self._decoded_failed)
        elif tab == "raw":
            self.raw.setPlainText("Carregando representação raw...")
            self._submit(lambda: self._session.get_raw_object(node.object_id),
                         lambda data: self.raw.setPlainText(_display_payload(data)), self._raw_failed)

    def _show_properties(self, node: StructureTreeNode | None) -> None:
        self.properties.clear()
        if node is None:
            return
        payload = node.payload
        if is_dataclass(payload):
            payload = asdict(payload)
        if node.object_id and self._session is not None and node.kind not in {"properties", "embedded", "metadata", "annotation", "signature"}:
            self._submit(lambda: self._session.get_object(node.object_id), self._populate_properties,
                         lambda category, message: self._populate_properties({"error": {"category": category, "message": message}}))
        else:
            self._populate_properties(payload or {"kind": node.kind, "object_id": node.object_id})

    def _populate_properties(self, value: object) -> None:
        self.properties.clear()
        _append_property_items(self.properties.invisibleRootItem(), value)
        self.properties.expandToDepth(1)
        self.properties.resizeColumnToContents(0)

    def _show_preview(self, result: object) -> None:
        data, asset = result
        image = QImage.fromData(data)
        if image.isNull():
            self.preview_label.setText(f"Preview binário disponível: {len(data):,} bytes")
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


class DeepFileExplorerPage(QWidget):
    def __init__(self, engine: DeepFileStructureEngine | None = None) -> None:
        super().__init__()
        self.engine = engine or DeepFileStructureEngine()
        self.thread_pool = QThreadPool.globalInstance()
        self._tasks: set[ExplorerTask] = set()
        self._result: AnalysisResult | None = None
        self._session: Any = None
        self._loaded_path: Path | None = None
        self.tree_model = StructureTreeModel()

        self.title = QLabel("Deep File Explorer")
        self.title.setObjectName("SectionTitle")
        self.file_label = QLabel("Selecione um PDF analisado.")
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

        upper = QSplitter(Qt.Horizontal)
        upper.addWidget(self.document_viewer)
        upper.addWidget(self.tree)
        upper.setStretchFactor(0, 3)
        upper.setStretchFactor(1, 2)
        upper.setSizes([760, 460])
        main_splitter = QSplitter(Qt.Vertical)
        main_splitter.addWidget(upper)
        main_splitter.addWidget(self.inspector)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 2)
        main_splitter.setSizes([500, 260])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.summary)
        layout.addWidget(self.status_label)
        layout.addWidget(main_splitter, 1)

        self.tree.selectionModel().currentChanged.connect(self._tree_selection_changed)
        self.search.returnPressed.connect(self.find_next)
        self.locate_page_button.clicked.connect(self.locate_current_page)

    def update_analysis(self, result: AnalysisResult) -> None:
        self._result = result
        path = Path(result.file_info.path)
        sha = getattr(getattr(result, "hashes", None), "sha256", "") or "—"
        self.file_label.setText(f"{result.file_info.name} · {result.file_info.size_bytes:,} bytes · SHA-256: {sha}")
        if path.suffix.lower() != ".pdf":
            self._session = None
            self._loaded_path = None
            self.status_label.setText("O Deep File Explorer V0.1 suporta PDF nesta versão.")
            self.document_viewer.clear("Visualização disponível apenas para PDF.")
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
        if path.suffix.lower() != ".pdf" or self._loaded_path == path:
            return
        self.status_label.setText("Carregando estrutura...")
        self.document_viewer.load(path)
        self._submit(lambda: self.engine.analyze_pdf(path), self._structure_loaded, self._structure_failed)

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

    def _structure_loaded(self, value: object) -> None:
        session = value
        self._session = session
        self._loaded_path = Path(self._result.file_info.path) if self._result else None
        self._set_model(StructureTreeModel(session.report))
        self.inspector.set_session(session)
        report = session.report
        summary = report.summary
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

    def _structure_failed(self, category: str, message: str) -> None:
        self._session = None
        self._loaded_path = None
        self.status_label.setText(
            f"Não foi possível construir a estrutura deste PDF. Categoria técnica: {category}. Detalhe: {message}"
        )

    def _tree_selection_changed(self, current: QModelIndex, _previous: QModelIndex) -> None:
        self.inspector.select_node(self.tree_model.node_from_index(current))

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

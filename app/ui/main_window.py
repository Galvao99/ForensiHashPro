from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QThread,
    QTimer,
    Qt,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService
from app.ui.sidebar import Sidebar
from app.ui.case_catalog import CaseCatalog, RecentCase
from app.ui.current_case_selection import CurrentCaseSelection
from app.ui.new_case_dialog import NewCaseDialog
from app.ui.line_icons import LineIcon
from app.ui.theme import load_desktop_stylesheet, theme_tokens
from app.settings import ApplicationPaths, SettingsService
from app.widgets.analysis_workspace import AnalysisWorkspace
from app.widgets.file_strip import FileStrip
from app.workers.analysis_worker import AnalysisWorker


class MainWindow(QWidget):
    def __init__(
        self,
        analysis_service: AnalysisService,
        *,
        paths: ApplicationPaths | None = None,
        settings_service: SettingsService | None = None,
    ) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.paths = paths or ApplicationPaths.discover()
        self.settings_service = settings_service or SettingsService(paths=self.paths)
        self.settings = self.settings_service.load()
        self.case_catalog = CaseCatalog(self.paths.recent_cases_file)
        self.current_case_name: str | None = None

        self.current_result: AnalysisResult | None = None
        self.current_selection: CurrentCaseSelection | None = None
        self.analysis_results: list[AnalysisResult] = []
        self.correlation_result = None
        self._case_result_cache: dict[str, dict[str, AnalysisResult]] = {}
        self._case_file_states: dict[str, str] = {}
        self._case_file_errors: dict[str, str] = {}
        self._case_progress: dict[str, object] = {}

        self.current_page_key = "home"
        self.current_folder_path: Path | None = None

        self.analysis_thread: QThread | None = None
        self.analysis_worker: AnalysisWorker | None = None

        self.progress_animation = QPropertyAnimation()
        self._sidebar_before_comparison_focus = False

        self.setWindowTitle(
            "ForensiHash Pro"
        )

        self.resize(
            1440,
            900,
        )

        # Permite uso em notebooks sem destruir o layout.
        self.setMinimumSize(
            960,
            640,
        )

        self.sidebar = Sidebar(
            self.paths, self.settings.theme_mode, self.settings.sidebar_groups
        )

        self.workspace = AnalysisWorkspace(
            self.analysis_service,
            theme_mode=self.settings.theme_mode,
        )
        self.file_strip = FileStrip(self.paths)

        self.clock_label = QLabel()
        self.clock_label.setObjectName(
            "ClockLabel"
        )
        self.clock_label.setAlignment(
            Qt.AlignmentFlag.AlignRight
        )

        self.page_title = QLabel(
            "Área inicial"
        )
        self.page_title.setObjectName(
            "PageTitle"
        )

        self.context_label = QLabel(
            "Nenhum arquivo selecionado"
        )
        self.context_label.setObjectName(
            "WorkspaceContextLabel"
        )

        self.status_label = QLabel(
            "Pronto"
        )
        self.status_label.setObjectName(
            "AnalysisStatusLabel"
        )

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName(
            "AnalysisProgressBar"
        )
        self.progress_bar.setRange(
            0,
            100,
        )
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(
            False
        )
        self.progress_bar.setVisible(
            False
        )

        self._build_ui()
        self._connect_signals()

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(
            self.update_clock
        )
        self.clock_timer.start(1000)

        self.update_clock()

        self.workspace.show_page(
            "home"
        )

        self.sidebar.set_active_page(
            "home"
        )
        self.workspace.home_page.set_recent_cases(self.case_catalog.list())
        self.workspace.home_page.set_case_open(False)
        self.case_icon.setVisible(False)
        self.page_title.setVisible(False)
        self.context_label.setVisible(False)

    # ==========================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==========================================================

    def _build_ui(self) -> None:
        """
        Constrói a janela utilizando um divisor horizontal.

        O usuário pode alterar manualmente a largura da sidebar
        e da área principal.
        """

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        main_layout.setSpacing(0)

        main_layout.addWidget(self._build_topbar())
        self.main_splitter = QSplitter(
            Qt.Orientation.Horizontal
        )
        self.main_splitter.setObjectName(
            "MainWindowSplitter"
        )

        # Evita que qualquer painel seja totalmente fechado.
        self.main_splitter.setChildrenCollapsible(
            False
        )

        self.content_widget = (
            self._build_content()
        )

        self.main_splitter.addWidget(
            self.sidebar
        )

        self.main_splitter.addWidget(
            self.content_widget
        )

        # Sidebar cresce menos.
        self.main_splitter.setStretchFactor(
            0,
            0,
        )

        # Workspace recebe o espaço excedente.
        self.main_splitter.setStretchFactor(
            1,
            1,
        )

        # Larguras iniciais.
        self.main_splitter.setSizes(
            [230, 1210]
        )

        main_layout.addWidget(
            self.main_splitter,
            stretch=1,
        )
        self.status_bar = self._build_statusbar()
        main_layout.addWidget(self.status_bar)

    def _build_topbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("TopBar")
        bar.setFixedHeight(60)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(18, 0, 14, 0)
        left = QWidget()
        left.setFixedWidth(260)
        left_layout = QHBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addStretch()
        center = QWidget()
        center_layout = QHBoxLayout(center)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(7)
        self.case_icon = LineIcon("briefcase", center, 17, paths=self.paths)
        self.case_icon.setObjectName("TopBarCaseIcon")
        self.topbar_context = QLabel("Nenhum Caso aberto")
        self.topbar_context.setObjectName("TopBarContext")
        center_layout.addStretch()
        center_layout.addWidget(self.case_icon)
        center_layout.addWidget(self.topbar_context)
        center_layout.addStretch()
        right = QWidget()
        right.setFixedWidth(260)
        right_layout = QHBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addStretch()
        self.help_button = QPushButton("?")
        self.help_button.setToolTip("Ajuda")
        self.help_button.setAccessibleName("Ajuda")
        self.settings_button = QPushButton("Configurações")
        self.settings_button.setAccessibleName("Configurações")
        self.settings_button.clicked.connect(lambda: self.show_workspace_page("settings"))
        right_layout.addWidget(self.help_button)
        right_layout.addWidget(self.settings_button)
        layout.addWidget(left)
        layout.addWidget(center, stretch=1)
        layout.addWidget(right)
        self._update_brand_assets(self.settings.theme_mode)
        return bar

    def _build_statusbar(self) -> QWidget:
        bar = QFrame()
        bar.setObjectName("StatusBar")
        bar.setFixedHeight(30)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(14, 0, 14, 0)
        self.operational_status_label = QLabel("Pronto")
        self.operational_status_label.setObjectName("StatusBarText")
        self.task_status_label = QLabel("0 tarefas em execução")
        self.task_status_label.setObjectName("StatusBarText")
        self.version_label = QLabel("v0.1.0")
        self.version_label.setObjectName("StatusBarVersion")
        self.current_analysis_file_label = QLabel()
        self.current_analysis_file_label.setObjectName("StatusCurrentFile")
        self.current_analysis_file_label.setMaximumWidth(360)
        self.current_analysis_file_label.setVisible(False)
        layout.addWidget(self.operational_status_label)
        layout.addWidget(self.task_status_label)
        layout.addStretch()
        layout.addWidget(self.current_analysis_file_label)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.version_label)
        return bar

    def _update_brand_assets(self, mode: str) -> None:
        self.sidebar.set_theme_mode(theme_tokens(mode).name)

    def _build_content(self) -> QWidget:
        """
        Cria a área principal do aplicativo.
        """

        content = QWidget()
        content.setObjectName(
            "Content"
        )

        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(12)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title_layout.addWidget(
            self.page_title
        )

        title_layout.addWidget(
            self.context_label
        )

        header.addLayout(
            title_layout
        )

        header.addStretch()

        header.addWidget(
            self.clock_label,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        layout.addLayout(header)

        self.progress_container = (
            self._build_progress_area()
        )

        layout.addWidget(
            self.workspace,
            stretch=1,
        )
        layout.addWidget(self.file_strip)

        return content

    def _build_progress_area(self) -> QWidget:
        """
        Cria o painel de progresso.
        """

        container = QFrame()
        container.setObjectName(
            "AnalysisProgressContainer"
        )
        container.setVisible(False)

        layout = QVBoxLayout(container)
        layout.setContentsMargins(
            12,
            6,
            12,
            6,
        )
        layout.setSpacing(4)

        layout.addWidget(
            self.status_label
        )

        layout.addWidget(
            self.progress_bar
        )

        return container

    # ==========================================================
    # SINAIS
    # ==========================================================

    def _connect_signals(self) -> None:
        """
        Conecta os eventos da interface.
        """

        self.sidebar.open_file_button.clicked.connect(
            self.select_file
        )

        self.sidebar.open_folder_button.clicked.connect(
            self.select_folder
        )

        self.file_strip.selection_requested.connect(self.select_file_from_strip)

        self.sidebar.navigation_requested.connect(
            self.show_workspace_page
        )

        self.sidebar.new_case_requested.connect(self.create_new_case)
        self.sidebar.open_case_requested.connect(self.open_existing_case)

        self.workspace.home_page.open_file_requested.connect(
            self.select_file
        )

        self.workspace.home_page.open_folder_requested.connect(
            self.select_folder
        )
        self.workspace.home_page.new_case_requested.connect(self.create_new_case)
        self.workspace.home_page.open_case_requested.connect(self.open_existing_case)
        self.workspace.home_page.dropped_paths.connect(self.create_new_case)
        self.workspace.home_page.recent_case_requested.connect(self.open_recent_case)
        self.workspace.home_page.navigation_requested.connect(self.show_workspace_page)
        self.workspace.settings_page.theme_requested.connect(self.set_theme_mode)
        self.workspace.timeline_page.source_requested.connect(
            self._navigate_timeline_source
        )
        self.workspace.comparison_page.focus_mode_requested.connect(
            self.set_comparison_focus_mode
        )
        self.workspace.correlation_explorer_page.artifact_requested.connect(
            self._select_correlation_artifact
        )
        self.workspace.correlation_explorer_page.source_requested.connect(
            self._open_correlation_source
        )
        self.sidebar.collapsed_changed.connect(
            self._resize_for_sidebar_state
        )
        self.sidebar.group_state_changed.connect(self._save_sidebar_group_state)

    def _save_sidebar_group_state(self, group: str, expanded: bool) -> None:
        self.settings.sidebar_groups[group] = expanded
        try:
            self.settings_service.save(self.settings)
        except OSError:
            # A preferência visual não deve interromper navegação nem análise.
            return

    def _resize_for_sidebar_state(self, collapsed: bool) -> None:
        available = max(1, self.main_splitter.width())
        sidebar_width = 64 if collapsed else min(300, max(280, available // 4))
        self.main_splitter.setSizes([sidebar_width, max(1, available - sidebar_width)])

    def set_comparison_focus_mode(self, enabled: bool) -> None:
        """Amplia a leitura do diff sem alterar o estado da comparação."""
        if enabled:
            self._sidebar_before_comparison_focus = self.sidebar.is_collapsed
            self.sidebar.set_collapsed(True)
        else:
            self.sidebar.set_collapsed(self._sidebar_before_comparison_focus)
        self.page_title.setVisible(not enabled)
        self.context_label.setVisible(not enabled and self.current_page_key != "general")
        self.clock_label.setVisible(not enabled)
        self.progress_container.setVisible(not enabled and self.progress_bar.isVisible())

    # ==========================================================
    # NAVEGAÇÃO
    # ==========================================================

    def show_workspace_page(
        self,
        page_key: str,
    ) -> None:
        """
        Exibe uma página do workspace.
        """

        if page_key in self.sidebar.CASE_ONLY_KEYS and self.current_case_name is None:
            self.context_label.setVisible(page_key != "general")
            return
        if not self.workspace.show_page(
            page_key
        ):
            return

        if page_key != "comparison" and self.workspace.comparison_page.focus_mode:
            self.workspace.comparison_page.set_focus_mode(False)

        self.current_page_key = page_key

        self.page_title.setVisible(True)

        self.page_title.setText(
            self.workspace.page_title(
                page_key
            )
        )

        # A Visão Geral já possui um header próprio para o artefato.
        # Nas páginas técnicas, o contexto compacto continua útil.
        self.context_label.setVisible(
            page_key != "general"
        )

        self.sidebar.set_active_page(
            page_key
        )

    def show_home_page(self) -> None:
        """
        Exibe a página inicial.
        """

        self.workspace.show_page(
            "home"
        )

        self.current_page_key = "home"

        self.page_title.setText(
            "Área inicial"
        )

        self.context_label.setVisible(True)

        self.page_title.setVisible(False)
        self.context_label.setVisible(False)

        self.sidebar.set_active_page("home")

    def _navigate_timeline_source(self, event_id: str) -> None:
        """Route to the closest real source page; no unsupported deep-link is implied."""
        if self.current_result is None:
            return
        event = next(
            (item for item in self.current_result.timeline_events if item.event_id == event_id),
            None,
        )
        if event is None:
            return
        target = {
            "metadata": "metadata",
            "filesystem_metadata": "metadata",
            "digital_signature": "digital_signature",
            "text": "ocr",
            "native": "ocr",
            "native_partial": "ocr",
            "ocr": "ocr",
            "filesystem": "general",
            "processing": "general",
        }.get(event.source_type)
        if target is not None:
            self.show_workspace_page(target)

    def set_theme_mode(self, mode: str) -> None:
        self.settings.theme_mode = mode
        try:
            self.settings_service.save(self.settings)
        except OSError as error:
            QMessageBox.warning(self, "Configurações", f"Não foi possível salvar a preferência: {error}")
            return
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(load_desktop_stylesheet(self.paths, theme_tokens(mode)))
        self._update_brand_assets(mode)
        self.sidebar.set_theme_mode(theme_tokens(mode).name)
        self.workspace.home_page.set_theme_mode(theme_tokens(mode).name)
        self.workspace.settings_page.set_theme_mode(mode)

    def create_new_case(self, dropped_paths: list[Path] | None = None) -> None:
        dialog = NewCaseDialog(self, list(dropped_paths or []))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._open_case_inputs(dialog.case_name, dialog.selected_paths)

    def open_existing_case(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Abrir Caso")
        if folder:
            self.create_new_case([Path(folder)])

    def open_recent_case(self, recent: RecentCase) -> None:
        path = Path(recent.source_path)
        if not path.exists():
            QMessageBox.warning(self, "Abrir Caso", "A localização registrada não está disponível.")
            self.workspace.home_page.set_recent_cases(self.case_catalog.list())
            return
        self._open_case_inputs(recent.name, [path])

    def _open_case_inputs(self, name: str, inputs: list[Path]) -> None:
        discovery_started = perf_counter()
        files: list[Path] = []
        for item in inputs:
            if item.is_dir():
                files.extend(path for path in item.rglob("*") if path.is_file())
            elif item.is_file():
                files.append(item)
        files = sorted(dict.fromkeys(files), key=lambda path: str(path).lower())
        if not files:
            QMessageBox.warning(self, "Novo Caso", "Nenhum arquivo disponível foi selecionado.")
            return
        self._last_ingestion_ms = (perf_counter() - discovery_started) * 1000
        self.current_case_name = name.strip()
        directory_inputs = [item for item in inputs if item.is_dir()]
        self.current_folder_path = directory_inputs[0] if len(inputs) == 1 and directory_inputs else None
        case_source = self.current_folder_path or files[0]
        self.file_strip.set_files(files)
        self.sidebar.set_case(self.current_case_name, len(files), "Pronto")
        self.topbar_context.setText(self.current_case_name)
        self.case_icon.setVisible(True)
        self.workspace.home_page.set_case_open(True)
        try:
            self.case_catalog.touch(self.current_case_name, case_source, len(files))
        except OSError as error:
            QMessageBox.warning(self, "Casos recentes", f"Não foi possível atualizar a lista: {error}")
        self.workspace.home_page.set_recent_cases(self.case_catalog.list())
        self.show_workspace_page("general")
        self._start_analysis(files=files)

    # ==========================================================
    # RELÓGIO
    # ==========================================================

    def update_clock(self) -> None:
        """
        Atualiza o relógio.
        """

        self.clock_label.setText(
            datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S"
            )
        )

    # ==========================================================
    # SELEÇÃO DE ARQUIVOS
    # ==========================================================

    def select_folder(self) -> None:
        """
        Abre uma pasta e inicia a análise.
        """

        folder = QFileDialog.getExistingDirectory(
            self,
            "Selecionar pasta",
        )

        if not folder:
            return

        folder_path = Path(folder)

        discovery_started = perf_counter()
        files = sorted(
            (
                path
                for path in folder_path.rglob("*")
                if path.is_file()
            ),
            key=lambda path: str(path).lower(),
        )
        self._last_ingestion_ms = (perf_counter() - discovery_started) * 1000

        self.current_folder_path = (
            folder_path
        )

        self.file_strip.set_files(files)

        self.context_label.setText(
            folder_path.name
        )

        self.workspace.home_page.update_workspace(
            file_count=len(files),
            folder_path=str(
                folder_path
            ),
        )

        self.show_home_page()

        self._start_analysis(
            files=files
        )

    def select_file(self) -> None:
        """
        Abre um único arquivo.
        """

        filename, _ = (
            QFileDialog.getOpenFileName(
                self,
                "Selecionar arquivo",
            )
        )

        if not filename:
            return

        file_path = Path(filename)

        self.current_folder_path = None
        self._last_ingestion_ms = 0.0

        self.file_strip.set_files([file_path])

        self._start_analysis(
            files=[file_path]
        )

    # ==========================================================
    # EXECUÇÃO DA ANÁLISE
    # ==========================================================

    def _start_analysis(
        self,
        *,
        files: list[Path],
    ) -> None:
        """
        Inicia a análise em uma thread separada.
        """

        if not files:
            self._show_status(
                "Nenhum arquivo disponível para análise.",
                progress=0,
            )
            return

        if (
            self.analysis_thread is not None
            and self.analysis_thread.isRunning()
        ):
            return

        self.analysis_results = []
        self.current_result = None
        self._case_file_errors = {}
        self.correlation_result = None

        case_id = (
            str(self.current_folder_path.resolve())
            if self.current_folder_path is not None
            else ""
        )
        cached_results = self._case_result_cache.get(case_id, {})
        current_keys = {str(path.resolve()) for path in files}
        cached_results = {
            key: value for key, value in cached_results.items()
            if key in current_keys and self._is_cached_result_valid(value)
        }
        if case_id:
            self._case_result_cache[case_id] = cached_results
        self._case_file_states = {
            str(path.resolve()): (
                "analyzed" if str(path.resolve()) in cached_results else "pending"
            )
            for path in files
        }
        selected_path = self.file_strip.selected_path()
        self.current_selection = (
            CurrentCaseSelection(
                case_id=case_id,
                file_path=selected_path,
                status=self._case_file_states.get(str(selected_path.resolve()), "pending"),
                result=cached_results.get(str(selected_path.resolve())),
            )
            if selected_path is not None else None
        )
        for path, status in self._case_file_states.items():
            self.file_strip.set_status(path, status)
        self._case_progress = {
            "case_name": self.current_case_name or (self.current_folder_path.name if self.current_folder_path else files[0].name),
            "is_case": self.current_folder_path is not None,
            "total": len(files),
            "analyzed": len(cached_results),
            "analyzing": 0,
            "pending": len(files) - len(cached_results),
            "failed": 0,
            "current_file": "",
            "file_paths": [str(path) for path in files],
        }
        self._refresh_case_overview()

        observability = getattr(self.analysis_service, "observability", None)
        case_identity = case_id or str(files[0].resolve())
        case_ref = (
            observability.begin_case(
                case_identity,
                [(str(path), path.stat().st_size) for path in files],
                getattr(self, "_last_ingestion_ms", 0.0),
            )
            if observability is not None else None
        )

        # Limpa IPs e dados investigativos da análise anterior.
        self.workspace.update_investigation_context(
            None
        )

        self._set_interface_busy(
            True
        )

        self._show_status(
            "Preparando análise...",
            progress=0,
        )

        self.analysis_thread = QThread(
            self
        )

        self.analysis_worker = AnalysisWorker(
            analysis_service=self.analysis_service,
            files=files,
            case_id=case_id or None,
            cached_results=cached_results,
            observability=observability,
        )
        self.analysis_worker.case_ref = case_ref

        self.analysis_worker.moveToThread(
            self.analysis_thread
        )

        self.analysis_thread.started.connect(
            self.analysis_worker.run
        )

        self.analysis_worker.progress_changed.connect(
            self._update_progress
        )

        self.analysis_worker.file_analyzed.connect(
            self._on_file_analyzed
        )

        self.analysis_worker.file_failed.connect(
            self._on_file_failed
        )
        self.analysis_worker.file_state_changed.connect(
            self._on_file_state_changed
        )
        self.analysis_worker.case_progress_changed.connect(
            self._on_case_progress_changed
        )

        self.analysis_worker.investigation_completed.connect(
            self._on_investigation_completed
        )

        self.analysis_worker.completed.connect(
            self._on_analysis_completed
        )

        self.analysis_worker.failed.connect(
            self._on_analysis_failed
        )

        self.analysis_worker.finished.connect(
            self.analysis_thread.quit
        )

        self.analysis_worker.finished.connect(
            self.analysis_worker.deleteLater
        )

        self.analysis_thread.finished.connect(
            self.analysis_thread.deleteLater
        )

        self.analysis_thread.finished.connect(
            self._on_thread_finished
        )

        self.analysis_thread.start()

    def _on_file_analyzed(
        self,
        result: AnalysisResult,
    ) -> None:
        """
        Recebe cada arquivo analisado.
        """

        result_key = str(Path(result.file_info.path).resolve())
        if not any(
            str(Path(item.file_info.path).resolve()) == result_key
            for item in self.analysis_results
        ):
            self.analysis_results.append(result)
        if self.current_folder_path is not None:
            case_id = str(self.current_folder_path.resolve())
            self._case_result_cache.setdefault(case_id, {})[result_key] = result

        if self.current_selection is not None and self.current_selection.key == result_key:
            self.current_selection.status = "analyzed"
            self.current_selection.result = result
            self.current_selection.error = None
            self._display_selected_result(result)
        self._refresh_case_overview()

    def _on_file_failed(
        self,
        file_path: str,
        error: str,
    ) -> None:
        """
        Registra falha em um arquivo específico.
        """

        print(
            f"Erro ao analisar {file_path}: "
            f"{error}"
        )
        key = str(Path(file_path).resolve())
        self._case_file_errors[key] = error
        if self.current_selection is not None and self.current_selection.key == key:
            self.current_selection.status = "failed"
            self.current_selection.result = None
            self.current_selection.error = error
            self.current_result = None
            self.workspace.clear_selected_analysis(Path(file_path), "failed", error)
            self.context_label.setText(f"{Path(file_path).name} • FALHA")
        self._refresh_case_overview()

    def _on_investigation_completed(
        self,
        correlation_result,
    ) -> None:
        """
        Recebe o resultado das correlações.
        """

        self.correlation_result = (
            correlation_result
        )

        self.workspace.update_investigation(
            current_result=(
                self.current_result
            ),
            correlation_result=(
                correlation_result
            ),
        )
        self._refresh_case_overview()

    def _on_analysis_completed(
        self,
        results: list[AnalysisResult],
    ) -> None:
        """
        Finaliza a análise completa.
        """

        self.analysis_results = list(
            results
        )

        if not self.analysis_results:
            self._show_status(
                "Nenhum arquivo pôde ser analisado.",
                progress=0,
            )
            return

        selected_result = self._selected_cached_result()
        self.current_result = selected_result

        self.workspace.update_hashes(
            self.analysis_results
        )

        if selected_result is not None:
            self._display_selected_result(selected_result)

        # Monta o contexto completo com OCR, IPs, hashes,
        # metadados, datas e demais dados estruturados.
        investigation_context = (
            self.analysis_service
            .build_investigation_context(
                self.analysis_results
            )
        )

        # Encaminha o contexto às páginas que precisam
        # dos dados estruturados, especialmente a aba IP.
        self.workspace.update_investigation_context(
            investigation_context
        )

        if self.correlation_result is not None:
            self.workspace.update_investigation(
                current_result=(
                    self.current_result
                ),
                correlation_result=(
                    self.correlation_result
                ),
            )
        self._refresh_case_overview()

        if self.current_folder_path is not None:
            if self.current_selection is not None:
                self.context_label.setText(
                    self.current_selection.file_path.name
                    if self.current_result is not None
                    else f"{self.current_selection.file_path.name} • {self.current_selection.status.upper()}"
                )
            else:
                self.context_label.setText(
                    f"{self.current_folder_path.name} • {len(self.analysis_results)} arquivo(s)"
                )

            self.workspace.home_page.update_workspace(
                file_count=len(
                    self.analysis_results
                ),
                folder_path=str(
                    self.current_folder_path
                ),
            )

        else:
            self.context_label.setText(
                self.current_result.file_info.name if self.current_result is not None else "Nenhum resultado"
            )

            self.workspace.home_page.update_workspace(
                file_name=(
                    self.current_result.file_info.name if self.current_result is not None else "Nenhum resultado"
                )
            )

        self._show_status(
            "Análise concluída.",
            progress=100,
        )

        QTimer.singleShot(
            900,
            self._hide_progress,
        )

    def _on_analysis_failed(
        self,
        error: str,
    ) -> None:
        """
        Exibe falha geral da análise.
        """

        self._show_status(
            f"Falha na análise: {error}",
            progress=0,
        )

    def _on_thread_finished(self) -> None:
        """
        Limpa as referências da thread.
        """

        self._set_interface_busy(
            False
        )

        self.analysis_thread = None
        self.analysis_worker = None

    # ==========================================================
    # SELEÇÃO DE RESULTADO JÁ ANALISADO
    # ==========================================================

    def analyze_selected_file(
        self,
        item,
    ) -> None:
        """
        Exibe o resultado correspondente ao arquivo selecionado.
        """

        if isinstance(item, Path):
            file_path = item
        else:
            raw_file_path = item.data(Qt.ItemDataRole.UserRole)
            if raw_file_path is None:
                return
            file_path = Path(str(raw_file_path))
        self.file_strip.set_selected_path(file_path)

        key = str(file_path.resolve())
        status = self._case_file_states.get(key, "pending")
        result = self._result_for_key(key)
        if result is not None:
            status = "analyzed"
        self.current_selection = CurrentCaseSelection(
            case_id=str(self.current_folder_path.resolve()) if self.current_folder_path else "",
            file_path=file_path,
            status=status,
            result=result,
            error=self._case_file_errors.get(key),
        )
        if result is not None:
            self._display_selected_result(result)
            return

        self.current_result = None
        self.workspace.clear_selected_analysis(file_path, status, self.current_selection.error)
        label = "FALHA" if status == "failed" else ("EM ANÁLISE" if status == "analyzing" else "PENDENTE")
        self.context_label.setText(f"{file_path.name} • {label}")

    def select_file_from_strip(self, file_path: Path) -> None:
        """Update canonical selection from the sole visual artifact navigator."""
        self.analyze_selected_file(file_path)

    def _select_correlation_artifact(self, file_path: str) -> None:
        """Use the canonical File Strip selection without leaving the Explorer."""
        self.analyze_selected_file(Path(file_path))

    def _open_correlation_source(self, file_path: str, occurrence_id: str) -> None:
        """Select the canonical artifact and open the available technical detail."""
        self.analyze_selected_file(Path(file_path))
        self.workspace.finding_page.set_navigation_context(file_path, occurrence_id)
        self.show_workspace_page("findings")

    def _on_file_state_changed(self, file_path: str, status: str) -> None:
        key = str(Path(file_path).resolve())
        self._case_file_states[key] = status
        self.file_strip.set_status(file_path, status)
        if self.current_selection is not None and self.current_selection.key == key:
            self.current_selection.status = status
            if status != "analyzed":
                self.current_selection.result = None
                self.current_result = None
                self.workspace.clear_selected_analysis(
                    Path(file_path), status, self._case_file_errors.get(key)
                )
        self._refresh_case_overview()

    def _result_for_key(self, key: str) -> AnalysisResult | None:
        if self.current_folder_path is not None:
            case_id = str(self.current_folder_path.resolve())
            cached = self._case_result_cache.get(case_id, {}).get(key)
            if cached is not None:
                return cached
        return next(
            (result for result in self.analysis_results
             if str(Path(result.file_info.path).resolve()) == key),
            None,
        )

    def _selected_cached_result(self) -> AnalysisResult | None:
        if self.current_selection is None:
            return None
        return self._result_for_key(self.current_selection.key)

    def _display_selected_result(self, result: AnalysisResult) -> None:
        self.current_result = result
        if self.current_selection is not None:
            self.current_selection.result = result
            self.current_selection.status = "analyzed"
        self.workspace.update_analysis(result)
        self.workspace.update_hashes(self.analysis_results)
        if self.correlation_result is not None:
            self.workspace.update_investigation(
                current_result=result,
                correlation_result=self.correlation_result,
            )
        self.context_label.setText(result.file_info.name)
        self.workspace.home_page.update_workspace(file_name=result.file_info.name)

    def _on_case_progress_changed(self, progress: object) -> None:
        if not isinstance(progress, dict):
            return
        self._case_progress.update(progress)
        if self.current_case_name:
            self._case_progress["case_name"] = self.current_case_name
        self._case_progress["analyzing"] = sum(
            status == "analyzing" for status in self._case_file_states.values()
        )
        self._set_current_analysis_file(str(self._case_progress.get("current_file", "")))
        self._refresh_case_overview()

    def _set_current_analysis_file(self, filename: str) -> None:
        self.current_analysis_file_label.setToolTip(filename)
        if not filename:
            self.current_analysis_file_label.clear()
            self.current_analysis_file_label.setVisible(False)
            return
        display = filename if len(filename) <= 48 else f"{filename[:45]}…"
        self.current_analysis_file_label.setText(f"Analisando: {display}")
        self.current_analysis_file_label.setVisible(True)

    def _refresh_case_overview(self) -> None:
        if not self._case_progress:
            return
        self.workspace.update_case(
            dict(self._case_progress),
            list(self.analysis_results),
            self.correlation_result,
        )
        if self.current_case_name:
            analyzed = int(self._case_progress.get("analyzed", 0))
            total = int(self._case_progress.get("total", 0))
            running = self.analysis_thread is not None and self.analysis_thread.isRunning()
            state = "Analisando" if running else "Pronto"
            self.sidebar.set_case(self.current_case_name, total, state)
            self.task_status_label.setText(
                self._progress_count_text(analyzed, total) if running else "0 tarefas em execução"
            )

    def _progress_count_text(self, analyzed: int, total: int) -> str:
        failed = int(self._case_progress.get("failed", 0))
        base = f"{analyzed} / {total} arquivos"
        return f"{base} · {failed} falha(s)" if failed else base

    @staticmethod
    def _is_cached_result_valid(result: AnalysisResult) -> bool:
        path = Path(result.file_info.path)
        try:
            stat = path.stat()
        except OSError:
            return False
        if stat.st_size != result.file_info.size_bytes:
            return False
        modified_at = result.file_info.modified_at
        if modified_at is None:
            return True
        return abs(stat.st_mtime - modified_at.timestamp()) < 0.001

    # ==========================================================
    # PROGRESSO
    # ==========================================================

    def _update_progress(
        self,
        value: int,
        message: str,
    ) -> None:
        """
        Atualiza suavemente a barra de progresso.
        """

        self.status_label.setText(
            message
        )
        self.operational_status_label.setText("Analisando")

        self.progress_bar.setVisible(
            True
        )
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedWidth(190)
        self.status_bar.setFixedHeight(38)

        self.progress_animation.stop()

        self.progress_animation = (
            QPropertyAnimation(
                self.progress_bar,
                b"value",
                self,
            )
        )

        self.progress_animation.setDuration(
            220
        )

        self.progress_animation.setStartValue(
            self.progress_bar.value()
        )

        self.progress_animation.setEndValue(
            max(
                0,
                min(
                    100,
                    value,
                ),
            )
        )

        self.progress_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self.progress_animation.start()

    def _show_status(
        self,
        message: str,
        progress: int,
    ) -> None:
        """
        Exibe o painel de progresso.
        """

        self._update_progress(
            progress,
            message,
        )

    def _hide_progress(self) -> None:
        """
        Oculta o painel de progresso.
        """

        self.progress_bar.setVisible(
            False
        )

        self.progress_container.setVisible(
            False
        )

        self.status_label.setText(
            "Pronto"
        )
        self.operational_status_label.setText("Pronto")
        self.task_status_label.setText("0 tarefas em execução")
        self._set_current_analysis_file("")
        self.status_bar.setFixedHeight(30)

    def _set_interface_busy(
        self,
        busy: bool,
    ) -> None:
        """
        Bloqueia os controles durante uma análise.
        """

        enabled = not busy

        self.sidebar.open_file_button.setEnabled(
            enabled
        )

        self.sidebar.open_folder_button.setEnabled(
            enabled
        )

        self.operational_status_label.setText("Analisando" if busy else "Pronto")
        if busy:
            total = int(self._case_progress.get("total", 0))
            analyzed = int(self._case_progress.get("analyzed", 0))
            self.task_status_label.setText(self._progress_count_text(analyzed, total))
        else:
            self.task_status_label.setText("0 tarefas em execução")
            self._set_current_analysis_file("")

    # ==========================================================
    # ENCERRAMENTO
    # ==========================================================

    def closeEvent(
        self,
        event,
    ) -> None:
        """
        Encerra a thread antes de fechar a aplicação.
        """

        if (
            self.analysis_worker is not None
            and self.analysis_thread is not None
            and self.analysis_thread.isRunning()
        ):
            self.analysis_worker.cancel()

            self.analysis_thread.quit()

            self.analysis_thread.wait(
                3000
            )

        super().closeEvent(event)

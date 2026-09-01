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
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from app.models import AnalysisResult
from app.services.analysis_service import AnalysisService
from app.ui.sidebar import Sidebar
from app.ui.current_case_selection import CurrentCaseSelection
from app.widgets.analysis_workspace import AnalysisWorkspace
from app.workers.analysis_worker import AnalysisWorker


class MainWindow(QWidget):
    def __init__(
        self,
        analysis_service: AnalysisService,
    ) -> None:
        super().__init__()

        self.analysis_service = analysis_service

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

        self.sidebar = Sidebar()

        self.workspace = AnalysisWorkspace(
            self.analysis_service
        )

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
            None
        )

    # ==========================================================
    # CONSTRUÇÃO DA INTERFACE
    # ==========================================================

    def _build_ui(self) -> None:
        """
        Constrói a janela utilizando um divisor horizontal.

        O usuário pode alterar manualmente a largura da sidebar
        e da área principal.
        """

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        main_layout.setSpacing(0)

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
            [320, 1120]
        )

        main_layout.addWidget(
            self.main_splitter
        )

    def _build_content(self) -> QWidget:
        """
        Cria a área principal do aplicativo.
        """

        content = QWidget()
        content.setObjectName(
            "Content"
        )

        layout = QVBoxLayout(content)
        layout.setContentsMargins(
            26,
            20,
            26,
            20,
        )
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
            self.progress_container
        )

        layout.addWidget(
            self.workspace,
            stretch=1,
        )

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

        self.sidebar.file_list.itemClicked.connect(
            self.analyze_selected_file
        )

        self.sidebar.navigation_requested.connect(
            self.show_workspace_page
        )

        self.workspace.home_page.open_file_requested.connect(
            self.select_file
        )

        self.workspace.home_page.open_folder_requested.connect(
            self.select_folder
        )
        self.workspace.comparison_page.focus_mode_requested.connect(
            self.set_comparison_focus_mode
        )
        self.sidebar.collapsed_changed.connect(
            self._resize_for_sidebar_state
        )

    def _resize_for_sidebar_state(self, collapsed: bool) -> None:
        available = max(1, self.main_splitter.width())
        sidebar_width = 64 if collapsed else min(300, max(260, available // 4))
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

        if not self.workspace.show_page(
            page_key
        ):
            return

        if page_key != "comparison" and self.workspace.comparison_page.focus_mode:
            self.workspace.comparison_page.set_focus_mode(False)

        self.current_page_key = page_key

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

        self.sidebar.set_active_page(
            None
        )

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

        self.sidebar.file_list.add_files(
            files
        )

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

        self.sidebar.file_list.add_files(
            [file_path]
        )

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
        selected_path = self.sidebar.file_list.selected_file_path()
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
            self.sidebar.file_list.set_file_status(path, status)
        self._case_progress = {
            "case_name": self.current_folder_path.name if self.current_folder_path else files[0].name,
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

        raw_file_path = item.data(
            Qt.ItemDataRole.UserRole
        )

        if raw_file_path is None:
            return

        file_path = Path(
            str(raw_file_path)
        )

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

    def _on_file_state_changed(self, file_path: str, status: str) -> None:
        key = str(Path(file_path).resolve())
        self._case_file_states[key] = status
        self.sidebar.file_list.set_file_status(file_path, status)
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
        self._case_progress["analyzing"] = sum(
            status == "analyzing" for status in self._case_file_states.values()
        )
        self._refresh_case_overview()

    def _refresh_case_overview(self) -> None:
        if not self._case_progress:
            return
        self.workspace.update_case(
            dict(self._case_progress),
            list(self.analysis_results),
            self.correlation_result,
        )

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

        self.progress_container.setVisible(
            True
        )

        self.progress_bar.setVisible(
            True
        )

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

        self.progress_container.setVisible(
            True
        )

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

        self.sidebar.file_list.setEnabled(True)
        self.sidebar.file_search.setEnabled(True)

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

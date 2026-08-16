from datetime import datetime
from pathlib import Path

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
        self.analysis_results: list[AnalysisResult] = []
        self.correlation_result = None

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

        files = sorted(
            (
                path
                for path in folder_path.rglob("*")
                if path.is_file()
            ),
            key=lambda path: str(path).lower(),
        )

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
        self.correlation_result = None

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
        )

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

        self.analysis_results.append(
            result
        )

        if self.current_result is None:
            self.current_result = result

            self.workspace.update_analysis(
                result
            )

            self.context_label.setText(
                result.file_info.name
            )

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

        self.current_result = (
            self.analysis_results[0]
        )

        self.workspace.update_hashes(
            self.analysis_results
        )

        self.workspace.update_analysis(
            self.current_result
        )

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

        if self.current_folder_path is not None:
            self.context_label.setText(
                (
                    f"{self.current_folder_path.name} • "
                    f"{len(self.analysis_results)} "
                    "arquivo(s)"
                )
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
                self.current_result.file_info.name
            )

            self.workspace.home_page.update_workspace(
                file_name=(
                    self.current_result.file_info.name
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

        for result in self.analysis_results:
            result_path = Path(
                result.file_info.path
            )

            if result_path == file_path:
                self.current_result = result

                self.workspace.update_analysis(
                    result
                )

                self.workspace.update_hashes(
                    self.analysis_results
                )

                if self.correlation_result is not None:
                    self.workspace.update_investigation(
                        current_result=result,
                        correlation_result=(
                            self.correlation_result
                        ),
                    )

                self.context_label.setText(
                    result.file_info.name
                )

                self.workspace.home_page.update_workspace(
                    file_name=(
                        result.file_info.name
                    )
                )

                return

        self._start_analysis(
            files=[file_path]
        )

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

        self.sidebar.file_list.setEnabled(
            enabled
        )

        self.sidebar.file_search.setEnabled(
            enabled
        )

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

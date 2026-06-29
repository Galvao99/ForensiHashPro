from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.engines.comparison_engine import ComparisonEngine
from app.services.analysis_service import AnalysisService
from app.services.export_service import ExportService
from app.ui.sidebar import Sidebar
from app.widgets.analysis_tabs import AnalysisTabs


class MainWindow(QWidget):
    """Janela principal do ForensiHash."""

    def __init__(self, analysis_service: AnalysisService) -> None:
        super().__init__()

        self.analysis_service = analysis_service

        self.current_result = None
        self.last_comparison_result = None

        self.comparison_engine = ComparisonEngine()
        self.export_service = ExportService()

        self.setWindowTitle("ForensiHash Pro")
        self.resize(850, 550)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("ClockLabel")

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.sidebar = Sidebar()
        self.sidebar.open_file_button.clicked.connect(self.select_file)
        self.sidebar.open_folder_button.clicked.connect(self.select_folder)
        self.sidebar.file_list.itemClicked.connect(self.analyze_selected_file)

        self.content = self._build_content()

        self.sidebar.compare_button.clicked.connect(self.compare_with_file)

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content, stretch=1)

        self.setLayout(main_layout)

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("Content")

        layout = QVBoxLayout()
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = QLabel("Análise de Arquivo")
        header.setObjectName("PageTitle")

        self.analysis_tabs = AnalysisTabs()

        layout.addWidget(header)
        layout.addWidget(self.clock_label)
        layout.addWidget(self.analysis_tabs, stretch=1)

        content.setLayout(layout)
        return content

    def update_clock(self) -> None:
        current_time = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.clock_label.setText(f"Horário: {current_time}")

    def select_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Selecionar Pasta")

        if not folder:
            return

        folder_path = Path(folder)

        files = [
            path
            for path in folder_path.rglob("*")
            if path.is_file()
        ]

        self.sidebar.file_list.add_files(files)

    def analyze_selected_file(self, item) -> None:
        file_path = item.data(1)
        self.analyze_file(file_path)

    def analyze_file(self, file_path: Path) -> None:
        result = self.analysis_service.analyze(file_path)
        self.current_result = result
        self.analysis_tabs.update_analysis(result)

    def select_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Selecionar Arquivo")

        if not filename:
            return

        self.analyze_file(Path(filename))

    def compare_with_file(self) -> None:
        if self.current_result is None:
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar arquivo para comparação",
        )

        if not filename:
            return

        right_result = self.analysis_service.analyze(Path(filename))

        comparison_result = self.comparison_engine.compare(
            self.current_result,
            right_result,
        )

        self.last_comparison_result = comparison_result
        self.analysis_tabs.comparison_page.update_comparison(comparison_result)
        self.analysis_tabs.show_comparison_tab()
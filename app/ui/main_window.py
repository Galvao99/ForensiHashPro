from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.services.analysis_service import AnalysisService
from app.ui.sidebar import Sidebar
from app.widgets.analysis_tabs import AnalysisTabs


class MainWindow(QWidget):
    def __init__(self, analysis_service: AnalysisService) -> None:
        super().__init__()

        self.analysis_service = analysis_service
        self.current_result = None
        self.analysis_results = []
        
        self.setWindowTitle("ForensiHash Pro")
        self.resize(1280, 820)
        self.setMinimumSize(1050, 700)

        self.clock_label = QLabel()
        self.clock_label.setObjectName("ClockLabel")
        self.clock_label.setAlignment(Qt.AlignRight)

        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()

        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.sidebar = Sidebar()
        self.content = self._build_content()

        self.sidebar.open_file_button.clicked.connect(self.select_file)
        self.sidebar.open_folder_button.clicked.connect(self.select_folder)
        self.sidebar.file_list.itemClicked.connect(self.analyze_selected_file)
        self.sidebar.compare_button.clicked.connect(
            self.analysis_tabs.show_comparison_tab
        )

        main_layout.addWidget(self.sidebar)
        main_layout.addWidget(self.content, stretch=1)

        self.setLayout(main_layout)

    def _build_content(self) -> QWidget:
        content = QWidget()
        content.setObjectName("Content")

        root_layout = QVBoxLayout()
        root_layout.setContentsMargins(28, 24, 28, 24)
        root_layout.setSpacing(16)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        header = QLabel("Análise de Arquivo")
        header.setObjectName("PageTitle")

        header_layout.addWidget(header)
        header_layout.addStretch()
        header_layout.addWidget(self.clock_label)

        self.analysis_tabs = AnalysisTabs(self.analysis_service)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setObjectName("MainScrollArea")
        scroll_area.setWidget(self.analysis_tabs)

        root_layout.addLayout(header_layout)
        root_layout.addWidget(scroll_area, stretch=1)

        content.setLayout(root_layout)
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

        self.analysis_results = []

        for file_path in files:
            try:
                result = self.analysis_service.analyze(file_path)
                self.analysis_results.append(result)
            except Exception as error:
                print(f"Erro ao analisar {file_path.name}: {error}")

        self.analysis_tabs.update_hashes(self.analysis_results)

        if self.analysis_results:
            self.current_result = self.analysis_results[0]
            self.analysis_tabs.update_analysis(self.current_result)

    def analyze_selected_file(self, item) -> None:
        file_path = Path(item.data(1))

        for result in self.analysis_results:
            if Path(result.file_info.path) == file_path:
                self.current_result = result
                self.analysis_tabs.update_analysis(result)
                self.analysis_tabs.update_hashes(self.analysis_results)
                return

        self.analyze_file(file_path)

    def select_file(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo",
        )

        if not filename:
            return

        self.analyze_file(Path(filename))

    def analyze_file(self, file_path: Path) -> None:
        try:
            result = self.analysis_service.analyze(file_path)

            self.current_result = result
            self.analysis_results = [result]

            self.sidebar.file_list.add_files([file_path])

            self.analysis_tabs.update_analysis(result)
            self.analysis_tabs.update_hashes(self.analysis_results)

        except Exception as error:
            print(f"Erro ao analisar {file_path.name}: {error}")
from PySide6.QtWidgets import QTabWidget

from app.models import AnalysisResult
from app.pages.finding_page import FindingPage
from app.pages.general_page import GeneralPage
from app.pages.hash_page import HashPage
from app.pages.metadata_page import MetadataPage
from app.pages.timeline_page import TimelinePage


class AnalysisTabs(QTabWidget):
    """Abas principais da área de análise."""

    def __init__(self) -> None:
        super().__init__()

        self.setObjectName("AnalysisTabs")

        self.general_page = GeneralPage()
        self.hash_page = HashPage()
        self.metadata_page = MetadataPage()
        self.finding_page = FindingPage()
        self.timeline_page = TimelinePage()

        self.addTab(self.general_page, "Geral")
        self.addTab(self.hash_page, "Hashes")
        self.addTab(self.metadata_page, "Metadados")
        self.addTab(self.finding_page, "Vestígios")
        self.addTab(self.timeline_page, "Timeline")

    def update_analysis(self, result: AnalysisResult) -> None:
        self.general_page.update_analysis(result)
        self.hash_page.update_analysis(result)
        self.metadata_page.update_analysis(result)
        self.finding_page.update_analysis(result)
        self.timeline_page.update_analysis(result)
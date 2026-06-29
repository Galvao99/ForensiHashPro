from PySide6.QtWidgets import QTabWidget

from app.models import AnalysisResult
from app.pages.finding_page import FindingPage
from app.pages.general_page import GeneralPage
from app.pages.hash_page import HashPage
from app.pages.metadata_page import MetadataPage
from app.pages.timeline_page import TimelinePage
from app.pages.magic_number_page import MagicNumberPage
from app.pages.digital_signature_pages import DigitalSignaturePage
from app.pages.comparison_workspace import ComparisonWorkspace
from app.services.analysis_service import AnalysisService


class AnalysisTabs(QTabWidget):
    """Abas principais da área de análise."""

    def __init__(self, analysis_service: AnalysisService) -> None:
        super().__init__()

        self.setObjectName("AnalysisTabs")

        self.general_page = GeneralPage()
        self.hash_page = HashPage()
        self.metadata_page = MetadataPage()
        self.finding_page = FindingPage()
        self.timeline_page = TimelinePage()
        self.magic_number_page = MagicNumberPage()
        self.digital_signature_page = DigitalSignaturePage()
        self.comparison_page = ComparisonWorkspace(analysis_service)

        self.addTab(self.general_page, "Geral")
        self.addTab(self.hash_page, "Hashes")
        self.addTab(self.metadata_page, "Metadados")
        self.addTab(self.finding_page, "Vestígios")
        self.addTab(self.timeline_page, "Timeline")
        self.addTab(self.magic_number_page, "Magic Number")
        self.addTab(self.digital_signature_page, "Assinatura Digital")
        self.addTab(self.comparison_page, "Comparação")

    def update_analysis(self, result: AnalysisResult) -> None:
        self.general_page.update_analysis(result)
        self.hash_page.update_analysis(result)
        self.metadata_page.update_analysis(result)
        self.finding_page.update_analysis(result)
        self.timeline_page.update_analysis(result)
        self.magic_number_page.update_analysis(result)
        self.digital_signature_page.update_analysis(result)

    def show_comparison_tab(self) -> None:
        self.setCurrentWidget(self.comparison_page)
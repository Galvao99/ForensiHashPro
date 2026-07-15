from PySide6.QtWidgets import QTabWidget

from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.pages.comparison_workspace import ComparisonWorkspace
from app.pages.digital_signature_pages import DigitalSignaturePage
from app.pages.finding_page import FindingPage
from app.pages.general_page import GeneralPage
from app.pages.hash_page import HashPage
from app.pages.integrity_page import IntegrityPage
from app.pages.ip_pages import IpPage
from app.pages.magic_number_page import MagicNumberPage
from app.pages.metadata_page import MetadataPage
from app.pages.ocr_page import OcrPage
from app.pages.timeline_page import TimelinePage
from app.services.analysis_service import AnalysisService


class AnalysisTabs(QTabWidget):
    """
    Abas principais da área de análise.
    """

    def __init__(
        self,
        analysis_service: AnalysisService,
    ) -> None:
        super().__init__()

        self.setObjectName("AnalysisTabs")

        self.general_page = GeneralPage()
        self.hash_page = HashPage()
        self.metadata_page = MetadataPage()
        self.finding_page = FindingPage()
        self.timeline_page = TimelinePage()
        self.magic_number_page = MagicNumberPage()
        self.digital_signature_page = DigitalSignaturePage()
        self.integrity_page = IntegrityPage()
        self.comparison_page = ComparisonWorkspace(
            analysis_service
        )
        self.ocr_page = OcrPage()
        self.ip_page = IpPage()

        self.addTab(self.general_page, "Geral")
        self.addTab(self.hash_page, "Hashes")
        self.addTab(self.metadata_page, "Metadados")
        self.addTab(self.finding_page, "Vestígios")
        self.addTab(self.timeline_page, "Timeline")
        self.addTab(
            self.magic_number_page,
            "Magic Number",
        )
        self.addTab(
            self.digital_signature_page,
            "Assinatura Digital",
        )
        self.addTab(
            self.integrity_page,
            "Integridade",
        )
        self.addTab(
            self.comparison_page,
            "Comparação",
        )
        self.addTab(
            self.ocr_page,
            "OCR e Busca",
        )
        self.addTab(
            self.ip_page,
            "🌐 IP",
        )

    def update_analysis(
        self,
        result: AnalysisResult,
    ) -> None:
        pages = (
            ("Geral", self.general_page),
            ("Metadados", self.metadata_page),
            ("Timeline", self.timeline_page),
            ("Magic Number", self.magic_number_page),
            (
                "Assinatura Digital",
                self.digital_signature_page,
            ),
            ("Integridade", self.integrity_page),
            ("OCR", self.ocr_page),
            ("IP", self.ip_page),
        )

        for page_name, page in pages:
            update_method = getattr(
                page,
                "update_analysis",
                None,
            )

            if not callable(update_method):
                continue

            try:
                update_method(result)

            except Exception as error:
                print(
                    f"Erro ao atualizar a página "
                    f"'{page_name}': {error}"
                )

        self.finding_page.update_analysis(result)

    def update_investigation(
        self,
        *,
        current_result: AnalysisResult | None,
        correlation_result: CorrelationResult,
    ) -> None:
        self.general_page.update_correlation_count(
            correlation_result.total_findings
        )
        self.finding_page.update_combined_results(
            analysis_result=current_result,
            correlation_result=correlation_result,
        )

    def update_hashes(
        self,
        results: list[AnalysisResult],
    ) -> None:
        self.hash_page.update_results(results)

    def show_comparison_tab(self) -> None:
        self.setCurrentWidget(
            self.comparison_page
        )

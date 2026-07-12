from PySide6.QtWidgets import QStackedWidget

from app.investigation.correlation_result import CorrelationResult
from app.models import AnalysisResult
from app.pages.comparison_workspace import ComparisonWorkspace
from app.pages.digital_signature_pages import DigitalSignaturePage
from app.pages.finding_page import FindingPage
from app.pages.general_page import GeneralPage
from app.pages.hash_page import HashPage
from app.pages.home_page import HomePage
from app.pages.integrity_page import IntegrityPage
from app.pages.ip_pages import IpPage
from app.pages.magic_number_page import MagicNumberPage
from app.pages.metadata_page import MetadataPage
from app.pages.ocr_page import OcrPage
from app.pages.timeline_page import TimelinePage
from app.services.analysis_service import AnalysisService


class AnalysisWorkspace(QStackedWidget):
    """
    Área central de navegação do ForensiHash.

    As páginas são trocadas pelo menu lateral, sem abas superiores.
    """

    PAGE_TITLES = {
        "home": "Área inicial",
        "general": "Visão geral",
        "hashes": "Hashes",
        "metadata": "Metadados",
        "findings": "Vestígios técnicos",
        "timeline": "Linha temporal",
        "magic_number": "Magic Number",
        "digital_signature": "Assinatura digital",
        "integrity": "Integridade",
        "comparison": "Comparação",
        "ocr": "OCR e busca",
        "ip": "Contexto de IP",
    }

    def __init__(
        self,
        analysis_service: AnalysisService,
    ) -> None:
        super().__init__()

        self.setObjectName("AnalysisWorkspace")

        self.home_page = HomePage()
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

        self.pages = {
            "home": self.home_page,
            "general": self.general_page,
            "hashes": self.hash_page,
            "metadata": self.metadata_page,
            "findings": self.finding_page,
            "timeline": self.timeline_page,
            "magic_number": self.magic_number_page,
            "digital_signature": self.digital_signature_page,
            "integrity": self.integrity_page,
            "comparison": self.comparison_page,
            "ocr": self.ocr_page,
            "ip": self.ip_page,
        }

        for page in self.pages.values():
            self.addWidget(page)

        self.show_page("home")

    def show_page(
        self,
        page_key: str,
    ) -> bool:
        page = self.pages.get(page_key)

        if page is None:
            return False

        self.setCurrentWidget(page)
        return True

    def page_title(
        self,
        page_key: str,
    ) -> str:
        return self.PAGE_TITLES.get(
            page_key,
            "ForensiHash Pro",
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
                "Assinatura digital",
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

        try:
            self.finding_page.update_analysis(
                result
            )

        except Exception as error:
            print(
                "Erro ao atualizar a página "
                f"'Vestígios': {error}"
            )

    def update_investigation(
        self,
        *,
        current_result: AnalysisResult | None,
        correlation_result: CorrelationResult,
    ) -> None:
        self.finding_page.update_combined_results(
            analysis_result=current_result,
            correlation_result=correlation_result,
        )

    def update_hashes(
        self,
        results: list[AnalysisResult],
    ) -> None:
        self.hash_page.update_results(results)
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QStackedWidget

from app.investigation.correlation_result import CorrelationResult
from app.investigation.investigation_context import (
    InvestigationContext,
)

from app.models import AnalysisResult
from app.pages.comparison_workspace import ComparisonWorkspace
from app.pages.correlation_explorer_page import CorrelationExplorerPage
from app.pages.digital_signature_pages import DigitalSignaturePage
from app.pages.deep_file_explorer_page import DeepFileExplorerPage
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
from app.pages.diagnostics_page import DiagnosticsPage
from app.pages.settings_page import SettingsPage
from app.observability import HealthCheckService, ObservabilityService
from app.ui.theme import theme_tokens
from app.correlation.v2.pipeline import CanonicalCasePipelineResult


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
        "deep_file_explorer": "Deep File Explorer",
        "integrity": "Integridade",
        "comparison": "Comparação",
        "correlations": "Correlações",
        "ocr": "OCR e busca",
        "ip": "Contexto de IP",
        "diagnostics": "Configurações > Diagnóstico",
        "settings": "Configurações",
    }
    FILE_SCOPED_PAGES = {
        "hashes", "metadata", "findings", "timeline", "magic_number",
        "digital_signature", "deep_file_explorer", "integrity", "ocr", "ip",
    }

    def __init__(
        self,
        analysis_service: AnalysisService,
        *,
        theme_mode: str = "light",
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
        self.magic_number_page.apply_theme(theme_tokens(theme_mode))
        self.digital_signature_page = DigitalSignaturePage()
        self.deep_file_explorer_page = DeepFileExplorerPage()
        self.integrity_page = IntegrityPage()
        # self.binary_structure_page = BinaryStructurePage()

        self.comparison_page = ComparisonWorkspace(
            analysis_service
        )
        self.correlation_explorer_page = CorrelationExplorerPage()

        self.ocr_page = OcrPage()
        self.ip_page = IpPage()
        observability = getattr(analysis_service, "observability", None) or ObservabilityService()
        health_checks = getattr(analysis_service, "health_checks", None) or HealthCheckService()
        self.diagnostics_page = DiagnosticsPage(observability, health_checks)
        self.settings_page = SettingsPage(theme_mode)

        self.pages = {
            "home": self.home_page,
            "general": self.general_page,
            "hashes": self.hash_page,
            "metadata": self.metadata_page,
            "findings": self.finding_page,
            "timeline": self.timeline_page,
            "magic_number": self.magic_number_page,
            "digital_signature": self.digital_signature_page,
            "deep_file_explorer": self.deep_file_explorer_page,
            "integrity": self.integrity_page,
            "comparison": self.comparison_page,
            "correlations": self.correlation_explorer_page,
            "ocr": self.ocr_page,
            "ip": self.ip_page,
            "diagnostics": self.diagnostics_page,
            "settings": self.settings_page,
            # "binary_structure": self.binary_structure_page,
        }

        self.selection_placeholder = QLabel()
        self.selection_placeholder.setObjectName("FileSelectionPlaceholder")
        self.selection_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_placeholder.setWordWrap(True)
        self._selection_message: str | None = None
        self._requested_page_key = "home"

        for page in self.pages.values():
            self.addWidget(page)
        self.addWidget(self.selection_placeholder)

        self.show_page("home")

    def show_page(
        self,
        page_key: str,
    ) -> bool:
        page = self.pages.get(page_key)

        if page is None:
            return False

        self._requested_page_key = page_key
        if page_key in self.FILE_SCOPED_PAGES and self._selection_message is not None:
            self.setCurrentWidget(self.selection_placeholder)
        else:
            self.setCurrentWidget(page)
        if page is self.home_page:
            self.deep_file_explorer_page.release_analysis()
        if page is self.deep_file_explorer_page:
            page.ensure_loaded()
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
        self._selection_message = None
        requested_page = self.pages.get(self._requested_page_key)
        if requested_page is not None:
            self.setCurrentWidget(requested_page)

        pages = (
            ("Geral", self.general_page),
            ("Metadados", self.metadata_page),
            ("Timeline", self.timeline_page),
            ("Magic Number", self.magic_number_page),
            (
                "Assinatura digital",
                self.digital_signature_page,
            ),
            ("Deep File Explorer", self.deep_file_explorer_page),
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

    def clear_selected_analysis(self, file_path: Path, status: str, error: str | None = None) -> None:
        """Hide stale file-scoped content while retaining case-wide batch data."""
        self.deep_file_explorer_page.release_analysis()
        labels = {
            "pending": "Pendente",
            "analyzing": "Em análise",
            "failed": "Falha na análise",
        }
        detail = f"\n\n{error}" if error else ""
        self._selection_message = (
            f"{file_path.name}\n\n{labels.get(status, status.title())}{detail}"
        )
        self.selection_placeholder.setText(self._selection_message)
        if self._requested_page_key in self.FILE_SCOPED_PAGES:
            self.setCurrentWidget(self.selection_placeholder)

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

    def update_investigation_context(
        self,
        context: InvestigationContext | None,
    ) -> None:
        """
        Encaminha o contexto investigativo completo para páginas
        que consomem dados estruturados da análise.

        Atualmente, a aba IP utiliza esse contexto para apresentar
        os endereços IPv4 e IPv6 detectados nos arquivos.
        """

        self.ip_page.set_investigation_context(
            context
        )

    def update_hashes(
        self,
        results: list[AnalysisResult],
    ) -> None:
        self.finding_page.set_display_paths(
            [
                result.file_info.path
                for result in results
            ]
        )

        self.hash_page.update_results(
            results
        )
        self.comparison_page.update_results(results)

    def update_case(
        self,
        state: dict[str, object],
        results: list[AnalysisResult],
        correlation_result: CorrelationResult | None,
        case_id: str | None = None,
        canonical_result: CanonicalCasePipelineResult | None = None,
        canonical_error: str | None = None,
    ) -> None:
        self.general_page.update_case(state, results, correlation_result)
        self.correlation_explorer_page.update_case(
            case_id, results, canonical_result, canonical_error,
        )

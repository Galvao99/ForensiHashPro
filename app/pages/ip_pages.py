from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.integrations.ip.ip_service import (
    IpAnalysisService,
)
from app.investigation.investigation_context import (
    InvestigationContext,
)
from app.models.detected_ip import (
    DetectedIp,
    IpClassification,
)


@dataclass(slots=True)
class DetectedIpGroup:
    """
    Agrupamento visual das ocorrências de um mesmo endereço IP.
    """

    address: str
    version: int
    classification: IpClassification

    occurrences: list[DetectedIp] = field(
        default_factory=list
    )

    files: dict[str, int] = field(
        default_factory=dict
    )

    @property
    def occurrence_count(self) -> int:
        return len(self.occurrences)

    @property
    def file_count(self) -> int:
        return len(self.files)


class DetectedIpCard(QFrame):
    """
    Card compacto de um endereço IP identificado na análise.
    """

    CLASSIFICATION_LABELS = {
        IpClassification.PUBLIC: "Público",
        IpClassification.PRIVATE: "Privado",
        IpClassification.CGNAT: "CGNAT",
        IpClassification.LOOPBACK: "Loopback",
        IpClassification.LINK_LOCAL: "Link-local",
        IpClassification.MULTICAST: "Multicast",
        IpClassification.RESERVED: "Reservado",
        IpClassification.UNSPECIFIED: "Não especificado",
    }

    def __init__(
        self,
        group: DetectedIpGroup,
        analyze_callback,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.group = group
        self.analyze_callback = analyze_callback

        self.setObjectName("DetectedIpCard")
        self.setProperty(
            "classification",
            group.classification.value,
        )

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Maximum,
        )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            12,
            10,
            12,
            10,
        )
        layout.setSpacing(8)

        header_layout = QHBoxLayout()
        header_layout.setSpacing(8)

        address_label = QLabel(
            self._display_address(
                self.group.address
            )
        )
        address_label.setObjectName(
            "DetectedIpAddress"
        )
        address_label.setToolTip(
            self.group.address
        )
        address_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        version_badge = QLabel(
            f"IPv{self.group.version}"
        )
        version_badge.setObjectName(
            "CompactBadge"
        )

        classification_badge = QLabel(
            self.CLASSIFICATION_LABELS.get(
                self.group.classification,
                self.group.classification.value,
            )
        )
        classification_badge.setObjectName(
            "CompactBadge"
        )

        header_layout.addWidget(
            address_label,
            1,
        )
        header_layout.addWidget(
            version_badge,
        )
        header_layout.addWidget(
            classification_badge,
        )

        count_text = (
            f"{self.group.occurrence_count} "
            f"{'ocorrência' if self.group.occurrence_count == 1 else 'ocorrências'}"
            " · "
            f"{self.group.file_count} "
            f"{'arquivo' if self.group.file_count == 1 else 'arquivos'}"
        )

        count_label = QLabel(count_text)
        count_label.setObjectName(
            "MutedText"
        )

        files_label = QLabel(
            self._format_files()
        )
        files_label.setObjectName(
            "DetectedIpFiles"
        )
        files_label.setWordWrap(True)

        analyze_button = QPushButton(
            "Analisar este IP"
        )
        analyze_button.setObjectName(
            "AnalyzeDetectedIpButton"
        )
        analyze_button.clicked.connect(
            self._request_analysis
        )

        layout.addLayout(
            header_layout
        )
        layout.addWidget(
            count_label
        )
        layout.addWidget(
            files_label
        )
        layout.addWidget(
            analyze_button
        )

    def _request_analysis(self) -> None:
        self.analyze_callback(
            self.group.address
        )

    def _format_files(self) -> str:
        if not self.group.files:
            return "Origem não identificada"

        file_entries = []

        for file_name, count in sorted(
            self.group.files.items()
        ):
            suffix = (
                "ocorrência"
                if count == 1
                else "ocorrências"
            )

            file_entries.append(
                f"{file_name} — {count} {suffix}"
            )

        return "\n".join(
            file_entries
        )

    @staticmethod
    def _display_address(
        address: str,
    ) -> str:
        """
        Mantém IPv4 completo e reduz somente IPv6 muito longo.
        O endereço completo permanece disponível no tooltip.
        """

        if ":" not in address:
            return address

        if len(address) <= 26:
            return address

        return (
            f"{address[:13]}"
            f"…"
            f"{address[-9:]}"
        )


class IpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.ip_service = IpAnalysisService()
        self.current_result = None
        self.current_context: (
            InvestigationContext | None
        ) = None

        self.detected_ip_groups: dict[
            str,
            DetectedIpGroup,
        ] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(
            24,
            24,
            24,
            24,
        )
        main_layout.setSpacing(18)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        main_layout.addWidget(
            left_panel,
            1,
        )
        main_layout.addWidget(
            right_panel,
            3,
        )

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName(
            "IpLeftPanel"
        )

        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        title = QLabel(
            "🌐 Consulta de IP"
        )
        title.setObjectName(
            "PageTitle"
        )

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText(
            "Digite um IPv4 ou IPv6..."
        )
        self.ip_input.returnPressed.connect(
            self.lookup_ip
        )

        self.search_button = QPushButton(
            "Consultar IP"
        )
        self.search_button.clicked.connect(
            self.lookup_ip
        )

        help_text = QLabel(
            "Consulte manualmente um endereço IP ou "
            "selecione um endereço identificado no "
            "conteúdo dos arquivos analisados."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName(
            "MutedText"
        )

        detected_title = QLabel(
            "IPs encontrados na análise"
        )
        detected_title.setObjectName(
            "SectionTitle"
        )

        self.detected_summary_label = QLabel(
            "Nenhum endereço IP identificado."
        )
        self.detected_summary_label.setObjectName(
            "MutedText"
        )
        self.detected_summary_label.setWordWrap(
            True
        )

        self.detected_scroll = QScrollArea()
        self.detected_scroll.setObjectName(
            "DetectedIpsScroll"
        )
        self.detected_scroll.setWidgetResizable(
            True
        )
        self.detected_scroll.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.detected_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.detected_container = QWidget()
        self.detected_container.setObjectName(
            "DetectedIpsContainer"
        )

        self.detected_layout = QVBoxLayout(
            self.detected_container
        )
        self.detected_layout.setContentsMargins(
            0,
            0,
            0,
            0,
        )
        self.detected_layout.setSpacing(10)
        self.detected_layout.addStretch()

        self.detected_scroll.setWidget(
            self.detected_container
        )

        layout.addWidget(title)
        layout.addWidget(
            self.ip_input
        )
        layout.addWidget(
            self.search_button
        )
        layout.addWidget(
            help_text
        )
        layout.addSpacing(16)
        layout.addWidget(
            detected_title
        )
        layout.addWidget(
            self.detected_summary_label
        )
        layout.addWidget(
            self.detected_scroll,
            1,
        )

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName(
            "IpRightPanel"
        )

        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        self.status_label = QLabel(
            "Nenhum IP selecionado"
        )
        self.status_label.setObjectName(
            "IpStatusTitle"
        )

        self.summary_label = QLabel(
            "Consulte manualmente um endereço IP ou "
            "selecione um IP identificado durante a "
            "análise documental."
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName(
            "MutedText"
        )

        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)

        self.json_box = QTextEdit()
        self.json_box.setReadOnly(True)
        self.json_box.setPlaceholderText(
            "JSON bruto da consulta aparecerá aqui."
        )

        layout.addWidget(
            self.status_label
        )
        layout.addWidget(
            self.summary_label
        )
        layout.addWidget(
            QLabel("Resultado técnico")
        )
        layout.addWidget(
            self.details_box,
            2,
        )
        layout.addWidget(
            QLabel("JSON bruto")
        )
        layout.addWidget(
            self.json_box,
            2,
        )

        return panel

    # ==========================================================
    # CONTEXTO INVESTIGATIVO
    # ==========================================================

    def set_investigation_context(
        self,
        context: InvestigationContext | None,
    ) -> None:
        """
        Atualiza os IPs apresentados com base no contexto da
        análise atual.
        """

        self.current_context = context

        self.detected_ip_groups = (
            self._build_detected_ip_groups(
                context
            )
            if context is not None
            else {}
        )

        self._render_detected_ip_cards()

    def clear_investigation_context(
        self,
    ) -> None:
        self.set_investigation_context(
            None
        )

    def _build_detected_ip_groups(
        self,
        context: InvestigationContext,
    ) -> dict[str, DetectedIpGroup]:
        groups: dict[
            str,
            DetectedIpGroup,
        ] = {}

        for evidence_key, occurrences in (
            context.detected_ip_details.items()
        ):
            display_name = (
                context.display_name_for(
                    evidence_key
                )
            )

            per_file_counts: dict[
                str,
                int,
            ] = defaultdict(int)

            for occurrence in occurrences:
                per_file_counts[
                    occurrence.address
                ] += 1

                group = groups.get(
                    occurrence.address
                )

                if group is None:
                    group = DetectedIpGroup(
                        address=occurrence.address,
                        version=occurrence.version,
                        classification=(
                            occurrence.classification
                        ),
                    )

                    groups[
                        occurrence.address
                    ] = group

                group.occurrences.append(
                    occurrence
                )

            for address, count in (
                per_file_counts.items()
            ):
                group = groups[address]
                group.files[display_name] = (
                    group.files.get(
                        display_name,
                        0,
                    )
                    + count
                )

        # Compatibilidade com contextos antigos que possuam apenas
        # detected_ips, sem detected_ip_details.
        for evidence_key, addresses in (
            context.detected_ips.items()
        ):
            display_name = (
                context.display_name_for(
                    evidence_key
                )
            )

            for address in addresses:
                if address in groups:
                    continue

                version = (
                    6
                    if ":" in address
                    else 4
                )

                groups[address] = (
                    DetectedIpGroup(
                        address=address,
                        version=version,
                        classification=(
                            IpClassification.PUBLIC
                        ),
                        occurrences=[],
                        files={
                            display_name: 1,
                        },
                    )
                )

        return dict(
            sorted(
                groups.items(),
                key=lambda item: (
                    item[1].version,
                    item[0],
                ),
            )
        )

    def _render_detected_ip_cards(
        self,
    ) -> None:
        self._clear_detected_ip_cards()

        groups = list(
            self.detected_ip_groups.values()
        )

        if not groups:
            self.detected_summary_label.setText(
                "Nenhum endereço IPv4 ou IPv6 válido "
                "foi identificado no texto analisado."
            )
            return

        total_occurrences = sum(
            max(
                group.occurrence_count,
                sum(group.files.values()),
            )
            for group in groups
        )

        self.detected_summary_label.setText(
            f"{len(groups)} "
            f"{'endereço identificado' if len(groups) == 1 else 'endereços identificados'}"
            f" · {total_occurrences} "
            f"{'ocorrência' if total_occurrences == 1 else 'ocorrências'}"
        )

        for group in groups:
            card = DetectedIpCard(
                group=group,
                analyze_callback=(
                    self.analyze_detected_ip
                ),
            )

            self.detected_layout.insertWidget(
                self.detected_layout.count() - 1,
                card,
            )

    def _clear_detected_ip_cards(
        self,
    ) -> None:
        while (
            self.detected_layout.count() > 1
        ):
            item = self.detected_layout.takeAt(
                0
            )

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

    # ==========================================================
    # CONSULTA
    # ==========================================================

    def analyze_detected_ip(
        self,
        address: str,
    ) -> None:
        """
        Seleciona um endereço identificado e reaproveita o fluxo
        atual de consulta.
        """

        self.ip_input.setText(
            address
        )

        self.lookup_ip()

    def lookup_ip(self) -> None:
        ip = self.ip_input.text().strip()

        if not ip:
            self._show_error(
                "Informe um endereço IP para consulta."
            )
            return

        self.search_button.setEnabled(
            False
        )
        self.search_button.setText(
            "Consultando..."
        )

        try:
            result = self.ip_service.analyze(
                ip
            )

            self.current_result = result
            self._render_result(
                result
            )

        except Exception as error:
            self._show_error(
                str(error)
            )

        finally:
            self.search_button.setEnabled(
                True
            )
            self.search_button.setText(
                "Consultar IP"
            )

    def _render_result(
        self,
        result: Any,
    ) -> None:
        severity_label = {
            "ok": "🟢 OK",
            "warning": "🟡 Atenção",
            "error": "🔴 Erro",
            "info": "🔵 Informação",
        }.get(
            result.severity,
            result.severity,
        )

        self.status_label.setText(
            f"{severity_label} — {result.ip}"
        )

        self.summary_label.setText(
            result.technical_summary
        )

        details = f"""
IP: {result.ip}
Versão: {result.ip_version or "Não identificada"}
Tipo de rede: {result.network_type or "Não identificado"}
Público: {"Sim" if result.is_public else "Não"}
Consulta externa realizada: {"Sim" if result.lookup_performed else "Não"}
Provedor da consulta: {result.provider or "Não identificado"}

Localização: {result.location_summary}
País: {result.country or "Não identificado"}
Estado/Região: {result.region or "Não identificado"}
Cidade: {result.city or "Não identificado"}
Latitude: {result.latitude if result.latitude is not None else "Não identificada"}
Longitude: {result.longitude if result.longitude is not None else "Não identificada"}

ISP: {result.isp or "Não identificado"}
Organização: {result.organization or "Não identificada"}
ASN: {result.asn or "Não identificado"}
Proxy: {"Sim" if result.is_proxy else "Não" if result.is_proxy is False else "Não identificado"}
Indicador de fraude fornecido pelo provedor: {result.fraud_score if result.fraud_score is not None else "Não informado"}

Observação técnica:
{result.message or "A geolocalização por IP possui natureza estimativa e não comprova, isoladamente, a localização física exata do usuário ou a posse do dispositivo."}
""".strip()

        self.details_box.setText(
            details
        )

        if result.raw:
            self.json_box.setText(
                json.dumps(
                    result.raw,
                    ensure_ascii=False,
                    indent=4,
                )
            )
        else:
            self.json_box.setText(
                "Consulta externa não realizada "
                "para este endereço IP."
            )

    def _show_error(
        self,
        message: str,
    ) -> None:
        self.status_label.setText(
            "🔴 Erro na consulta"
        )
        self.summary_label.setText(
            message
        )
        self.details_box.clear()
        self.json_box.clear()
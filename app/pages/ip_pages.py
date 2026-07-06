import json

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.integrations.ip.ip_service import IpAnalysisService


class IpPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.ip_service = IpAnalysisService()
        self.current_result = None

        self._build_ui()

    def _build_ui(self) -> None:
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(18)

        left_panel = self._build_left_panel()
        right_panel = self._build_right_panel()

        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(right_panel, 3)

    def _build_left_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("IpLeftPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        title = QLabel("🌐 Consulta de IP")
        title.setObjectName("PageTitle")

        self.ip_input = QLineEdit()
        self.ip_input.setPlaceholderText("Digite um IPv4 ou IPv6...")

        self.search_button = QPushButton("Consultar IP")
        self.search_button.clicked.connect(self.lookup_ip)

        help_text = QLabel(
            "Use esta área para consultar manualmente um IP encontrado "
            "em contrato, log, trilha de eventos ou fonte externa."
        )
        help_text.setWordWrap(True)
        help_text.setObjectName("MutedText")

        detected_title = QLabel("IPs encontrados na análise")
        detected_title.setObjectName("SectionTitle")

        self.detected_ips_box = QTextEdit()
        self.detected_ips_box.setReadOnly(True)
        self.detected_ips_box.setPlaceholderText(
            "Futuramente, os IPs extraídos do OCR/logs aparecerão aqui."
        )

        layout.addWidget(title)
        layout.addWidget(self.ip_input)
        layout.addWidget(self.search_button)
        layout.addWidget(help_text)
        layout.addSpacing(16)
        layout.addWidget(detected_title)
        layout.addWidget(self.detected_ips_box)
        layout.addStretch()

        return panel

    def _build_right_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("IpRightPanel")

        layout = QVBoxLayout(panel)
        layout.setSpacing(14)

        self.status_label = QLabel("Nenhum IP selecionado")
        self.status_label.setObjectName("IpStatusTitle")

        self.summary_label = QLabel(
            "Consulte manualmente um endereço IP ou selecione um IP identificado "
            "durante a análise documental."
        )
        self.summary_label.setWordWrap(True)
        self.summary_label.setObjectName("MutedText")

        self.details_box = QTextEdit()
        self.details_box.setReadOnly(True)

        self.json_box = QTextEdit()
        self.json_box.setReadOnly(True)
        self.json_box.setPlaceholderText("JSON bruto da consulta aparecerá aqui.")

        layout.addWidget(self.status_label)
        layout.addWidget(self.summary_label)
        layout.addWidget(QLabel("Resultado técnico"))
        layout.addWidget(self.details_box, 2)
        layout.addWidget(QLabel("JSON bruto"))
        layout.addWidget(self.json_box, 2)

        return panel

    def lookup_ip(self) -> None:
        ip = self.ip_input.text().strip()

        if not ip:
            self._show_error("Informe um endereço IP para consulta.")
            return

        try:
            result = self.ip_service.analyze(ip)
            self.current_result = result
            self._render_result(result)

        except Exception as error:
            self._show_error(str(error))

    def _render_result(self, result) -> None:
        severity_label = {
            "ok": "🟢 OK",
            "warning": "🟡 Atenção",
            "error": "🔴 Erro",
            "info": "🔵 Informação",
        }.get(result.severity, result.severity)

        self.status_label.setText(f"{severity_label} — {result.ip}")
        self.summary_label.setText(result.technical_summary)

        details = f"""
IP: {result.ip}
Versão: {result.ip_version or "Não identificada"}
Tipo de rede: {result.network_type or "Não identificado"}
Público: {"Sim" if result.is_public else "Não"}
Consulta externa realizada: {"Sim" if result.lookup_performed else "Não"}

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

Observação técnica:
{result.message or "A geolocalização por IP possui natureza estimativa e não comprova, isoladamente, a localização física exata do usuário ou a posse do dispositivo."}
""".strip()

        self.details_box.setText(details)

        if result.raw:
            self.json_box.setText(
                json.dumps(result.raw, ensure_ascii=False, indent=4)
            )
        else:
            self.json_box.setText("Consulta externa não realizada para este endereço IP.")

    def _show_error(self, message: str) -> None:
        self.status_label.setText("🔴 Erro na consulta")
        self.summary_label.setText(message)
        self.details_box.clear()
        self.json_box.clear()
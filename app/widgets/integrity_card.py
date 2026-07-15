from PySide6.QtWidgets import QLabel

from app.models import AnalysisResult
from app.models.digital_signature_result import (
    SignatureAnalysisStatus,
)
from app.widgets.base_card import BaseCard


class IntegrityCard(BaseCard):
    def __init__(self):
        super().__init__("🛡 Verificações técnicas")

        self.content = QLabel("Nenhuma análise realizada.")
        self.content.setWordWrap(True)
        self.content.setObjectName("CardContent")
        self.body_layout.addWidget(self.content)

    def update_integrity(self, result: AnalysisResult) -> None:
        integrity = result.integrity
        lines = [
            self._line(
                "Hash calculado",
                "Sim" if integrity.hash_verified else "Não",
            ),
            self._line(
                "Magic number",
                "Compatível"
                if integrity.magic_number_verified
                else "Incompatível ou não identificado",
            ),
            self._line(
                "Estrutura PDF",
                self._tristate(
                    integrity.is_structurally_valid,
                    true="Válida nos critérios verificados",
                    false="Inválida nos critérios verificados",
                ),
            ),
            self._line(
                "Assinatura digital",
                self._signature_status(
                    integrity.digital_signature_analysis_status
                ),
            ),
            self._line(
                "Criptografia PDF",
                self._detected(integrity.encrypted),
            ),
            self._line(
                "JavaScript PDF",
                self._detected(integrity.javascript_detected),
            ),
            self._line(
                "Arquivos incorporados",
                self._detected(integrity.embedded_files),
            ),
            self._line(
                "Atualizações incrementais",
                "Não aplicável"
                if integrity.incremental_updates is None
                else str(integrity.incremental_updates),
            ),
        ]

        self.content.setText("\n\n".join(lines))

    @staticmethod
    def _line(label: str, value: str) -> str:
        return f"{label}: {value}"

    @staticmethod
    def _tristate(
        value: bool | None,
        *,
        true: str,
        false: str,
    ) -> str:
        if value is True:
            return true
        if value is False:
            return false
        return "Não aplicável"

    @staticmethod
    def _detected(value: bool | None) -> str:
        if value is True:
            return "Detectado"
        if value is False:
            return "Não detectado"
        return "Não aplicável"

    @staticmethod
    def _signature_status(
        status: SignatureAnalysisStatus | None,
    ) -> str:
        labels = {
            SignatureAnalysisStatus.PRESENT: "Presente",
            SignatureAnalysisStatus.ABSENT: "Ausente",
            SignatureAnalysisStatus.NOT_APPLICABLE: "Não aplicável",
            SignatureAnalysisStatus.UNSUPPORTED: "Formato não suportado",
            SignatureAnalysisStatus.ERROR: "Não foi possível analisar",
        }
        return labels.get(status, "Não analisada")

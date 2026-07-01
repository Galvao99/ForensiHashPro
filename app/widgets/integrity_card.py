from PySide6.QtWidgets import QLabel

from app.engines.score_engine import ScoreEngine
from app.models import AnalysisResult
from app.widgets.base_card import BaseCard


class IntegrityCard(BaseCard):
    def __init__(self):
        super().__init__("🛡 Integridade")

        self.score_engine = ScoreEngine()

        self.content = QLabel("Nenhuma análise realizada.")
        self.content.setWordWrap(True)
        self.content.setObjectName("CardContent")

        self.body_layout.addWidget(self.content)

    def update_integrity(self, result: AnalysisResult) -> None:
        score_result = self.score_engine.calculate(result)

        text = f"""Score Geral

{score_result.score}/100 • Risco {score_result.risk_level} • Confiança {score_result.confidence_level}

--------------------------
"""

        for section in score_result.sections:
            icon = self._icon(section.score, section.exists)

            text += f"""

{icon} {section.name}
Score: {section.score}/100
Peso: {section.weight}

{section.description}
"""

            if section.details:
                text += "\nDetalhes:\n"
                for detail in section.details[:5]:
                    text += f"- {detail}\n"

        text += """

--------------------------

Observação técnica

O hash não compõe o score pericial isoladamente, pois atua como fingerprint do arquivo. Seu valor avaliativo ocorre principalmente em comparação, cadeia de custódia ou verificação de alteração posterior.
"""

        self.content.setText(text)

    def _icon(self, score: int, exists: bool) -> str:
        if not exists:
            return "❌"

        if score >= 85:
            return "✅"

        if score >= 65:
            return "⚠️"

        return "❌"
from PySide6.QtWidgets import QLabel

from app.models.comparison_result import ComparisonResult
from app.widgets.base_card import BaseCard


class ComparisonCard(BaseCard):
    
    def __init__(self) -> None:
        super().__init__("⚖ Comparação Forense")

        self.content = QLabel("Comparação ainda não realizada.")
        self.content.setObjectName("CardContent")
        self.content.setWordWrap(True)

        self.body_layout.addWidget(self.content)

    def update_comparison(self, result: ComparisonResult) -> None:
        lines = [
            f"Arquivo A: {result.left_file}",
            f"Arquivo B: {result.right_file}",
            "",
            "Resultado:",
            result.technical_summary,
            "",
        ]

        for section in result.sections:
            icon = {
                "success": "✅",
                "warning": "⚠️",
                "critical": "❌",
                "info": "ℹ️",
            }.get(section.status, "ℹ️")

            lines.append(f"{icon} {section.title}")
            lines.append(section.description)
            lines.append("")

        self.content.setText("\n".join(lines))
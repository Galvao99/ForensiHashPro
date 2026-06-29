import json
from pathlib import Path

from app.models.comparison_result import ComparisonResult


class ExportService:
    def export_comparison_txt(self, result: ComparisonResult, output_path: Path) -> None:
        lines = [
            "ForensiHash Pro - Relatório de Comparação",
            "",
            f"Arquivo A: {result.left_file}",
            f"Arquivo B: {result.right_file}",
            "",
            "Resumo Técnico:",
            result.technical_summary,
            "",
            "Seções:",
        ]

        for section in result.sections:
            lines.append(f"- {section.title}: {section.status}")
            lines.append(f"  {section.description}")

        output_path.write_text("\n".join(lines), encoding="utf-8")

    def export_comparison_json(self, result: ComparisonResult, output_path: Path) -> None:
        data = {
            "left_file": result.left_file,
            "right_file": result.right_file,
            "technical_summary": result.technical_summary,
            "sections": [
                {
                    "title": s.title,
                    "status": s.status,
                    "description": s.description,
                }
                for s in result.sections
            ],
        }

        output_path.write_text(
            json.dumps(data, indent=4, ensure_ascii=False),
            encoding="utf-8",
        )
"""Deterministic synthetic Qt visual matrix; never opens evidence.

Run: .venv/Scripts/python scripts/review_diagnostics.py
Captures and geometry results are local, ignored development artifacts.
"""

from __future__ import annotations
# ruff: noqa: E402 -- standalone tool sets its local import root and Qt platform first.

import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from app.observability.models import (
    ComponentHealth,
    CorrelationRuleMetric,
    ExecutionMetric,
    ExecutionStatus,
    OperationalStatus,
)
from app.observability.service import ObservabilityService
from app.pages.diagnostics_page import DiagnosticsPage
from app.settings import ApplicationPaths
from app.ui.theme import DARK_THEME, LIGHT_THEME, load_desktop_stylesheet


class Checks:
    def run(self):
        return ()


def sample_service() -> ObservabilityService:
    service = ObservabilityService()
    now = datetime.now(timezone.utc)
    ref = service.begin_case(
        "visual-fixture", [("a", 800_000_000), ("b", 1_000_000)], 142.0, cache_entries=1
    )
    service.set_components(
        (
            ComponentHealth(
                "ocr",
                "OCR — reconhecimento de caracteres em documentos digitalizados",
                OperationalStatus.OK,
                now,
            ),
            ComponentHealth("exiftool", "ExifTool", OperationalStatus.UNAVAILABLE, now),
        )
    )
    for index, (engine, duration, file_id) in enumerate(
        (
            ("ocr", 15_900, "file_a"),
            ("metadata", 310, "file_a"),
            ("hash", 90, "file_a"),
            ("analysis_pipeline", 18_400, "file_a"),
            ("metadata", 210, "file_b"),
            ("analysis_pipeline", 900, "file_b"),
        )
    ):
        service.record_metric(
            ExecutionMetric(
                f"sample_{index}",
                engine,
                now,
                duration_ms=duration,
                status=ExecutionStatus.COMPLETED,
                file_ref=file_id,
                case_ref=ref,
                operation=engine,
                bytes_read=800_000_000 if engine == "hash" else None,
                metadata={"size_bytes": 800_000_000 if file_id == "file_a" else 1_000_000},
            )
        )
    service.record_correlation(
        facts=321_000,
        occurrences=921_234,
        relations=451_000,
        duration_ms=740,
        index_ms=81,
        rules_ms=310,
        rules=(
            CorrelationRuleMetric("case.declared_hash_verification", 120, 2),
            CorrelationRuleMetric("case.document_date_metadata_temporal_relation", 190, 4),
        ),
    )
    service.record_error(
        component_id="ocr",
        operation="ocr_image",
        error_code="ocr_timeout",
        error=RuntimeError("Synthetic private name /secret/path 123.456.789-00"),
    )
    service.update_case(
        completed=2,
        partial=0,
        failed=0,
        pending=0,
        running=0,
        cache_hits=1,
        cache_misses=1,
        first_result=True,
        finished=True,
    )
    return service


def main() -> None:
    app = QApplication.instance() or QApplication([])
    font_path = Path("C:/Windows/Fonts/segoeui.ttf")
    if font_path.exists():
        QFontDatabase.addApplicationFont(str(font_path))
    app.setFont(QFont("Segoe UI", 10))
    output = ROOT / ".review_tmp" / "diagnostics"
    output.mkdir(parents=True, exist_ok=True)
    report = []
    for theme in (LIGHT_THEME, DARK_THEME):
        app.setStyleSheet(load_desktop_stylesheet(ApplicationPaths.discover(), theme))
        for width in (700, 900, 1200, 1366):
            page = DiagnosticsPage(sample_service(), Checks())
            page.timer.stop()
            page.resize(width, 768)
            page.show()
            for _ in range(8):
                app.processEvents()
            views = (
                (0, "overview", None),
                (1, "performance", None),
                (2, "engine-detail", page.engine_details),
                (1, "artifact-detail", page.artifact_details),
                (4, "errors", None),
                (5, "environment", None),
            )
            for tab, name, detail in views:
                page.tabs.setCurrentIndex(tab)
                if tab == 2:
                    page.engine_filter.setCurrentIndex(page.engine_filter.findData("ocr"))
                    page.components.selectRow(0)
                elif tab == 1:
                    page.artifacts.selectRow(0)
                for _ in range(8):
                    app.processEvents()
                scroll = page.tabs.widget(tab)
                scroll.verticalScrollBar().setValue(0)
                if detail is not None:
                    scroll.ensureWidgetVisible(detail, 0, 8)
                page.refresh_button.setFocus()
                app.processEvents()
                filename = f"{theme.name}-{width}-{name}.png"
                page.grab().save(str(output / filename))
                report.append(
                    {
                        "file": filename,
                        "requested_width": width,
                        "width": page.width(),
                        "viewport_width": scroll.viewport().width(),
                        "body_width": scroll.widget().width(),
                        "horizontal_overflow": scroll.horizontalScrollBar().maximum(),
                    }
                )
            page.close()
            page.deleteLater()
            app.processEvents()
    (output / "geometry.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "captures": len(report),
                "overflow": [
                    row
                    for row in report
                    if row["horizontal_overflow"] or row["width"] != row["requested_width"]
                ],
                "fonts": QFontDatabase.families()[:10],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

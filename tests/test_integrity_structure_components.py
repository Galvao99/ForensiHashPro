import ast
from pathlib import Path

import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QWidget

from app.models.binary_finding import BinaryFinding
from app.models.pdf_raw_analysis_result import (
    PdfRawAnalysisResult,
    PdfRawObject,
    PdfStartXref,
)
from app.presentation.pdf_raw_technical_formatter import PdfRawTechnicalFormatter
from app.widgets.flow_layout import FlowLayout
from app.widgets.raw_technical_data_panel import RawTechnicalDataPanel
from app.widgets.technical_metric_badge import TechnicalMetricBadge


@pytest.fixture(scope="module")
def qt_app():
    app = QApplication.instance() or QApplication([])
    yield app


def test_flow_layout_wraps_badges_without_overlap(qt_app) -> None:
    container = QWidget()
    layout = FlowLayout(container, horizontal_spacing=8, vertical_spacing=8)
    items = [
        TechnicalMetricBadge(str(index), f"Métrica {index}", str(index))
        for index in range(6)
    ]
    for item in items:
        layout.addWidget(item)

    container.resize(300, 400)
    container.show()
    layout.setGeometry(QRect(0, 0, 300, layout.heightForWidth(300)))
    qt_app.processEvents()

    geometries = [item.geometry() for item in items]
    assert all(geometry.width() >= 0 for geometry in geometries)
    assert all(geometry.height() >= 0 for geometry in geometries)
    assert all(
        not left.intersects(right)
        for index, left in enumerate(geometries)
        for right in geometries[index + 1 :]
    )
    assert len({geometry.y() for geometry in geometries}) > 1


def test_raw_panel_preserves_and_copies_exact_text(qt_app) -> None:
    panel = RawTechnicalDataPanel()
    copied: list[bool] = []
    closed: list[bool] = []
    text = "linha 1\n  linha 2\n"
    panel.copied.connect(lambda: copied.append(True))
    panel.close_requested.connect(lambda: closed.append(True))

    assert not panel.isVisible()
    assert not panel.copy_button.isEnabled()
    panel.set_text(text)
    panel.copy_to_clipboard()
    assert panel.technical_text() == text
    assert QApplication.clipboard().text() == text
    assert copied == [True]

    panel.open_panel()
    panel.request_close()
    assert closed == [True]
    assert not panel.isVisible()
    panel.clear()
    assert panel.technical_text() == ""
    assert not panel.copy_button.isEnabled()


def test_formatter_uses_real_model_fields_and_contains_no_qt_dependency() -> None:
    result = PdfRawAnalysisResult(
        version="1.7",
        header_offset=5,
        objects=[PdfRawObject(4, 0, 20, 80, True)],
        stream_count=1,
        trailer_offsets=[100],
        startxrefs=[PdfStartXref(120, 100)],
        eof_offsets=[140],
        encrypted=True,
        has_javascript=True,
        findings=[
            BinaryFinding("fact", "Fato estrutural", "Descrição factual", 140)
        ],
    )

    text = PdfRawTechnicalFormatter().format(result)

    assert "PDF 1.7" in text
    assert "5 (0x5)" in text
    assert "4 0 obj" in text
    assert any(
        line.split() == ["Quantidade", "1"] for line in text.splitlines()
    )
    assert "trailer @ 100 (0x64)" in text
    assert "offset declarado: 100 (0x64)" in text
    assert "%%EOF @ 140 (0x8C)" in text
    assert any(
        line.split() == ["JavaScript", "detectado"]
        for line in text.splitlines()
    )
    assert "Fato estrutural: Descrição factual" in text
    source = Path("app/presentation/pdf_raw_technical_formatter.py").read_text(
        encoding="utf-8"
    )
    assert "PySide6" not in source
    assert "parser" not in source.lower()
    assert "engine" not in source.lower()


def test_integrity_presentation_does_not_import_parser_or_engine() -> None:
    presentation_files = (
        Path("app/pages/integrity_page.py"),
        Path("app/widgets/document_structure_card.py"),
        Path("app/widgets/raw_technical_data_panel.py"),
        Path("app/presentation/pdf_raw_technical_formatter.py"),
    )

    imported_modules: set[str] = set()
    for path in presentation_files:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported_modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported_modules.add(node.module)

    assert not any("parser" in module for module in imported_modules)
    assert not any(module.startswith("app.engines") for module in imported_modules)

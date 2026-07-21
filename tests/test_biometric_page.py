from datetime import datetime
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from app.models import (
    AnalysisResult,
    DigitalSignatureResult,
    FileInfo,
    HashResult,
    MagicNumberResult,
    MetadataResult,
)
from app.models.biometric_report import (
    BiometricAlgorithmResult,
    BiometricConstraint,
    BiometricConstraintEvaluation,
    BiometricDecision,
    BiometricEvidence,
    BiometricMetric,
    BiometricReport,
    ConstraintEvaluationStatus,
)
from app.models.integrity_result import IntegrityResult
from app.pages.biometric_page import BiometricPage
from app.widgets.analysis_tabs import AnalysisTabs


@pytest.fixture(scope="module")
def qt_app():
    return QApplication.instance() or QApplication([])


def _report() -> BiometricReport:
    width = BiometricMetric(
        "IMAGE_WIDTH",
        400,
        canonical_name="image.width_pixels",
        category="IMAGE_GEOMETRY",
        source_path="$.metrics[0]",
    )
    yaw = BiometricMetric(
        "POSE_ANGLE_YAW",
        0,
        canonical_name="face.pose.yaw_degrees",
        category="FACE_CHARACTERISTICS",
        source_path="$.metrics[1]",
    )
    demographic = BiometricMetric(
        "ESTIMATED_AGE",
        30,
        category="DEMOGRAPHICS",
        source_path="$.metrics[2]",
    )
    width_constraint = BiometricConstraint(
        "image_width",
        canonical_name="image.width_pixels",
        minimum=480,
        preferred=640,
        maximum=800,
    )
    yaw_constraint = BiometricConstraint(
        "pose_angle_yaw",
        canonical_name="face.pose.yaw_degrees",
        minimum=-30,
        preferred=0,
        maximum=30,
    )
    return BiometricReport(
        provider="Aware",
        product="KnomiFaceLiveness Library",
        version="3.12.3",
        workflow="charlie4",
        timestamps={"date": datetime(2025, 1, 1)},
        decisions=[
            BiometricDecision(
                "liveness_result",
                "LIVE",
                metadata={"score": 100.0, "score_frr": 1.28},
            )
        ],
        algorithms=[
            BiometricAlgorithmResult(
                "N4", category="configured", threshold=50
            ),
            BiometricAlgorithmResult(
                "N4", category="result", score=11, threshold=50
            ),
            BiometricAlgorithmResult(
                "Fused Score", category="result", score=25.7
            ),
        ],
        metrics=[width, yaw, demographic],
        constraints=[width_constraint, yaw_constraint],
        constraint_evaluations=[
            BiometricConstraintEvaluation(
                width,
                width_constraint,
                400,
                "pixels",
                ConstraintEvaluationStatus.BELOW_MINIMUM,
                "Abaixo do mínimo.",
            ),
            BiometricConstraintEvaluation(
                yaw,
                yaw_constraint,
                0,
                "degrees",
                ConstraintEvaluationStatus.PREFERRED,
                "Preferencial.",
            ),
        ],
        evidences=[
            BiometricEvidence(
                "face_image",
                "/remote/ANONYMIZED/images",
                metadata={"count": 1, "frames": [{"timestamp": 123.0}]},
            )
        ],
        metadata={
            "faceliveness_library": {"revision": "r170888"},
            "video_library": {
                "product": "Aware Video Library",
                "version": "6.13.1.1",
                "revision": "r161312",
            },
            "profile_name": "knomi_charlie_server.xml",
            "images_count": 1,
            "autocapture": {
                "captured_frame_index": 0,
                "captured_frame_is_constructed": False,
            },
            "workflow_parameters": {
                "security_level": 70,
                "jpeg_quality_level": 90,
                "face_detection_mode": "DOMINANT_FACE_BY_SIZE",
            },
        },
        raw_payload={"server": "face_liveness", "task": "analyze_video"},
    )


def _result(report: BiometricReport | None) -> AnalysisResult:
    return AnalysisResult(
        file_info=FileInfo("sample.json", Path("sample.json"), ".json", 1),
        hashes=HashResult("a", "b", "c", "d", "e", "f"),
        metadata=MetadataResult(),
        findings=[],
        magic_numbers=MagicNumberResult(
            detected_type="JSON",
            signature="",
            extension_matches=True,
        ),
        digital_signature=DigitalSignatureResult(has_signature=False),
        integrity=IntegrityResult(
            score=0,
            technical_status="Factual",
            is_structurally_valid=None,
            hash_verified=True,
            magic_number_verified=True,
            digital_signature_present=False,
        ),
        biometric_report=report,
    )


def _text(widget) -> str:
    return "\n".join(label.text() for label in widget.findChildren(QLabel))


def test_tab_is_dynamic_without_reprocessing(qt_app) -> None:
    tabs = AnalysisTabs(analysis_service=object())
    assert tabs.indexOf(tabs.biometric_page) == -1
    tabs.update_analysis(_result(_report()))
    assert tabs.tabText(tabs.indexOf(tabs.biometric_page)) == "Biometria"
    tabs.update_analysis(_result(None))
    assert tabs.indexOf(tabs.biometric_page) == -1


def test_decision_header_technical_and_missing_values(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    text = _text(page)
    for expected in (
        "Aware",
        "KnomiFaceLiveness Library",
        "3.12.3 r170888",
        "charlie4",
        "LIVE",
        "Resultado declarado pelo fornecedor",
        "não reproduzido independentemente pelo ForensiHash",
        "DOMINANT_FACE_BY_SIZE",
    ):
        assert expected in text
    assert "None" not in text
    assert "null" not in text


def test_algorithms_keep_fused_score_without_artificial_threshold(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    text = _text(page.algorithms_card)
    assert "Algoritmos configurados" in text
    assert "N4" in text
    assert "Score: 11" in text
    assert "Fused Score · Score: 25.7 · Threshold: Não informado" in text
    assert "passou" not in text.casefold()
    assert "falhou" not in text.casefold()


def test_metrics_hide_demographics_and_support_filters(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    text = _text(page.metrics_card)
    assert "IMAGE_WIDTH" in text
    assert "POSE_ANGLE_YAW" in text
    assert "ESTIMATED_AGE" not in text
    assert "DEMOGRAPHICS" not in text
    page.metric_search.setText("yaw")
    visible = [row.isHidden() for row, *_ in page.metric_rows]
    assert visible == [True, False]
    page.metric_search.clear()
    index = page.metric_category.findData("IMAGE_GEOMETRY")
    page.metric_category.setCurrentIndex(index)
    visible = [row.isHidden() for row, *_ in page.metric_rows]
    assert visible == [False, True]


def test_restrictions_hide_normal_states_until_show_all(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    states = {
        status: row
        for row, status in page.restriction_rows
    }
    assert states[ConstraintEvaluationStatus.BELOW_MINIMUM].isHidden() is False
    assert states[ConstraintEvaluationStatus.PREFERRED].isHidden() is True
    page.show_all_constraints.setChecked(True)
    assert states[ConstraintEvaluationStatus.PREFERRED].isHidden() is False


def test_remote_evidence_has_no_open_button(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    text = _text(page.evidences_card)
    assert "/remote/ANONYMIZED/images" in text
    assert "não foi disponibilizado localmente" in text
    assert page.evidences_card.findChildren(QPushButton) == []


def test_empty_page_is_defensive(qt_app) -> None:
    page = BiometricPage()
    page.set_report(None)
    assert page.stack.currentIndex() == 0
    assert "Nenhum relatório biométrico reconhecido" in _text(page)


def test_header_reflows_without_fixed_width(qt_app) -> None:
    page = BiometricPage()
    page.set_report(_report())
    page.resize(700, 800)
    page.show()
    qt_app.processEvents()
    first = page.header_grid.getItemPosition(0)
    second = page.header_grid.getItemPosition(1)
    assert first[:2] == (0, 0)
    assert second[:2] == (1, 0)
    page.resize(1100, 800)
    qt_app.processEvents()
    second = page.header_grid.getItemPosition(1)
    assert second[:2] == (0, 1)
    page.close()

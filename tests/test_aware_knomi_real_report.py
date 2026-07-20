import json
from pathlib import Path

from app.biometric.parsers import AwareKnomiReportParser, BiometricParserRegistry
from app.models.biometric_report import ConstraintEvaluationStatus
from app.rules.biometric_report_rule import BiometricReportRule
from app.services.biometric_report_service import BiometricReportService


FIXTURE = Path("tests/fixtures/biometrics/aware_knomi_report.json")


def _report():
    return BiometricReportService(
        BiometricParserRegistry([AwareKnomiReportParser()])
    ).parse(FIXTURE)


def test_versions_workflow_and_profile_metadata() -> None:
    report = _report()
    assert report.provider == "Aware"
    assert report.product == "KnomiFaceLiveness Library"
    assert report.version == "3.12.3"
    assert report.workflow == "charlie4"
    assert report.metadata["faceliveness_library"]["revision"] == "r170888"
    assert report.metadata["video_library"] == {
        "product": "Aware Video Library",
        "version": "6.13.1.1",
        "revision": "r161312",
        "raw": "Aware Video Library, version 6.13.1.1 r161312",
    }
    assert report.metadata["profile_name"] == "knomi_charlie_server.xml"
    parameters = report.metadata["workflow_parameters"]
    assert parameters["security_level"] == 70
    assert parameters["jpeg_quality_level"] == 90
    assert parameters["face_detection_mode"] == "DOMINANT_FACE_BY_SIZE"


def test_configured_and_returned_algorithms_thresholds_and_fused_score() -> None:
    report = _report()
    configured = [item for item in report.algorithms if item.category == "configured"]
    returned = [item for item in report.algorithms if item.category == "result"]
    assert len(configured) == 5
    assert len(returned) == 8
    assert next(item for item in returned if item.original_name == "N4").threshold == 50
    fused = next(item for item in returned if item.original_name == "Fused Score")
    assert fused.score == 25.7
    assert fused.threshold is None
    assert fused.source_path == "$.result.algorithm_results[7]"


def test_liveness_autocapture_images_frames_and_timestamps() -> None:
    report = _report()
    decision = report.decisions[0]
    assert decision.value == "LIVE"
    assert decision.metadata["score"] == 100.0
    assert decision.metadata["score_frr"] == 1.28
    assert decision.source_path == "$.result.liveness_result"
    assert report.metadata["autocapture"] == {
        "captured_frame_index": 0,
        "captured_frame_is_constructed": False,
        "feedback": [],
    }
    assert report.metadata["images_count"] == 1
    evidence = report.evidences[0]
    assert evidence.original_reference.endswith("/ANONYMIZED/1683645440696")
    assert evidence.source_path == "$.images.path"
    assert evidence.resolved_path is None
    assert evidence.metadata["frames"][0]["timestamp"] == 1683645439.0
    assert report.analysis_date is not None
    assert "workflow.frames[0].timestamp" in report.timestamps


def test_real_metric_categories_aliases_unknown_and_demographics() -> None:
    report = _report()
    by_name = {metric.original_name: metric for metric in report.metrics}
    expected = {
        "IMAGE_WIDTH": "image.width_pixels",
        "IMAGE_HEIGHT": "image.height_pixels",
        "EYE_SEPARATION": "face.eye_separation_pixels",
        "POSE_ANGLE_YAW": "face.pose.yaw_degrees",
        "POSE_ANGLE_PITCH": "face.pose.pitch_degrees",
        "EYE_AXIS_ANGLE": "face.pose.roll_degrees",
        "FILE_SIZE": "file.size_bytes",
        "BRIGHTNESS_SCORE": "image.brightness_score",
        "SHARPNESS_LIKELIHOOD": "image.sharpness_likelihood",
        "FOCUS_LIKELIHOOD": "image.focus_likelihood",
        "MASK_LIKELIHOOD": "face.mask_likelihood",
        "DARK_GLASSES_LIKELIHOOD": "face.dark_glasses_likelihood",
    }
    for original, canonical in expected.items():
        assert by_name[original].canonical_name == canonical
    assert by_name["NUMBER_CHANNELS"].canonical_name is None
    assert by_name["NUMBER_CHANNELS"].category == "IMAGE_CHARACTERISTICS"
    assert by_name["ESTIMATED_AGE"].canonical_name is None
    assert by_name["ESTIMATED_AGE"].category == "DEMOGRAPHICS"
    assert by_name["POSE_ANGLE_YAW"].source_path.startswith(
        "$.result.captured_frame_metrics_result["
    )


def test_real_profile_pref_qweight_and_limit_shapes() -> None:
    report = _report()
    constraints = {item.original_name: item for item in report.constraints}
    yaw = constraints["pose_angle_yaw"]
    assert (yaw.minimum, yaw.preferred, yaw.maximum) == (-30, 0, 30)
    assert yaw.raw_data["qWeight"] == "1.0"
    assert constraints["eye_separation"].minimum == 90
    assert constraints["eye_separation"].preferred is None
    assert constraints["image_width"].minimum is None
    assert constraints["image_width"].preferred == 480
    assert constraints["image_width"].maximum is None


def test_constraint_statuses_and_missing_metric_are_factual() -> None:
    report = _report()
    statuses = {evaluation.status for evaluation in report.constraint_evaluations}
    assert ConstraintEvaluationStatus.PREFERRED in statuses
    assert ConstraintEvaluationStatus.WITHIN_RANGE in statuses
    findings = BiometricReportRule().apply(report)
    assert any(
        finding.title == "Métrica necessária não disponibilizada"
        for finding in findings
    )
    left_eye = next(
        evaluation
        for evaluation in report.constraint_evaluations
        if evaluation.metric.original_name
        == "LEFT_EYE_CLOSED_LIKELIHOOD"
    )
    assert left_eye.constraint.original_name == "left_eye_closed_likelihood"
    assert left_eye.status is ConstraintEvaluationStatus.PREFERRED


def test_findings_use_real_facts_without_demographic_or_independent_claims() -> None:
    findings = BiometricReportRule().apply(_report())
    titles = {finding.title for finding in findings}
    assert {
        "Versão declarada",
        "Score declarado pelo fornecedor",
        "Quantidade de imagens declarada",
        "Frame capturado declarado",
        "Frame declarado como não construído",
    } <= titles
    rendered = " ".join(
        f"{finding.title} {finding.description}"
        for finding in findings
    ).casefold()
    for prohibited in (
        "estimated_age",
        "demographics",
        "raça",
        "sexo",
        "identidade confirmada",
        "fraude detectada",
        "pessoa viva",
    ):
        assert prohibited not in rendered


def test_fixture_is_anonymized_and_contains_no_embedded_image() -> None:
    text = FIXTURE.read_text(encoding="utf-8")
    payload = json.loads(text)
    assert payload["input"]["meta_data"]["username"] == "ANONYMIZED_USER"
    assert "ANONYMIZED" in payload["images"]["path"]
    assert "base64" not in text.casefold()

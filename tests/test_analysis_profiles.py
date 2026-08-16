from pathlib import Path

from app.analysis_profiles import (
    AnalysisCapability,
    FORENSIHASH_FREE,
    FORENSIHASH_PRO,
)
from app.factory.application_factory import ApplicationFactory
from app.contracts import LegacyAnalysisAdapter
from app.evidence import EvidenceManager


def test_profiles_define_a_real_execution_boundary() -> None:
    assert FORENSIHASH_FREE.max_artifacts == 1
    assert FORENSIHASH_FREE.allows(AnalysisCapability.HASHING)
    assert FORENSIHASH_FREE.allows(AnalysisCapability.METADATA)
    assert FORENSIHASH_FREE.allows(AnalysisCapability.STRUCTURE)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.OCR)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.ENTITY_EXTRACTION)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.IP_ANALYSIS)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.TEMPORAL_ANALYSIS)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.CROSS_ARTIFACT_CORRELATION)
    assert not FORENSIHASH_FREE.allows(AnalysisCapability.BIOMETRIC_ANALYSIS)
    assert all(FORENSIHASH_PRO.allows(item) for item in AnalysisCapability)


def test_free_factory_does_not_initialize_heavy_content_services() -> None:
    service = ApplicationFactory.create_analysis_service(FORENSIHASH_FREE)

    assert service.text_extraction_service is None
    assert service.entity_extraction_service is None
    assert service.timeline_service is None


def test_free_pipeline_skips_pro_engines_and_keeps_basic_analysis(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.txt"
    artifact.write_text("contato perito@example.test 192.0.2.10", encoding="utf-8")
    service = ApplicationFactory.create_analysis_service(FORENSIHASH_FREE)
    service.evidence_manager = EvidenceManager(tmp_path / "evidence")

    result = service.analyze(artifact)
    by_code = {step.code: step for step in result.processing_steps}

    assert result.hashes.md5 and result.hashes.sha1 and result.hashes.sha256
    assert result.metadata is not None
    assert result.resolved_entities == []
    assert result.timeline_events == []
    assert result.biometric_report is None
    for code in (
        "text_extraction",
        "ocr",
        "entity_resolution",
        "ip_context",
        "timeline",
        "biometric_analysis",
    ):
        assert by_code[code].status.value == "skipped"
        assert by_code[code].safe_details["reason"] == "capability_not_enabled"

    contract = LegacyAnalysisAdapter().convert(result)
    assert contract.schema_version == "1.0.0"
    assert contract.execution["analysis_profile"] == "free"
    assert contract.ocr is None
    assert contract.timeline is None
    assert contract.biometrics is None


def test_free_correlation_is_rejected_before_rules_execute() -> None:
    service = ApplicationFactory.create_analysis_service(FORENSIHASH_FREE)

    try:
        service.correlate([])
    except PermissionError as error:
        assert "não habilitada" in str(error)
    else:
        raise AssertionError("O perfil Free não pode executar correlação.")

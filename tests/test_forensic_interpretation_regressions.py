from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.engines.pdf_structure_engine import PDFStructureEngine
from app.enum.severity import Severity
from app.integrations.ip.ip_client import Ip2LocationClient
from app.investigation.investigation_context import InvestigationContext
from app.investigation.rules.metadata_contract_date_rule import (
    MetadataContractDateRule,
)
from app.investigation.rules.producer_context_rule import ProducerContextRule
from app.models import AnalysisResult, MetadataResult
from app.rules.producer_rule import ProducerRule
from app.rules.suspicious_software_rule import SuspiciousSoftwareRule


@pytest.mark.parametrize(
    "producer",
    ("iText 7", "Microsoft Word", "LibreOffice", "Ghostscript 10"),
)
def test_producer_alone_is_only_technical_information(producer: str) -> None:
    metadata = MetadataResult(raw={"PDF:Producer": producer})
    findings = ProducerRule().apply(metadata)
    findings.extend(SuspiciousSoftwareRule().apply(metadata))

    assert findings
    assert all(finding.severity is Severity.INFO for finding in findings)
    assert not any(
        claim in finding.description.lower()
        for finding in findings
        for claim in ("fraude comprovada", "adulteração comprovada")
    )


def test_missing_optional_metadata_does_not_allege_tampering() -> None:
    finding = ProducerRule().apply(MetadataResult(raw={}))[0]

    assert finding.severity is Severity.INFO
    assert "não indica fraude" in finding.description.lower()


def test_xref_stream_is_recognized_without_traditional_trailer(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "xref-stream.pdf"
    pdf.write_bytes(
        b"%PDF-1.7\n4 0 obj\n<< /Type /XRef /Length 1 >>\n"
        b"stream\nx\nendstream\nendobj\nstartxref\n9\n%%EOF\n"
    )

    result = PDFStructureEngine().analyze(pdf)

    assert result.xref_stream_found is True
    assert result.traditional_xref_found is False
    assert result.xref_found is True
    assert result.trailer_found is False
    assert result.parser_limitations


def test_incremental_markers_are_factual_not_a_validity_conclusion(
    tmp_path: Path,
) -> None:
    pdf = tmp_path / "incremental.pdf"
    pdf.write_bytes(
        b"%PDF-1.7\nxref\n0 1\ntrailer\n<<>>\nstartxref\n9\n%%EOF\n"
        b"1 0 obj\n<< /Type /Sig >>\nendobj\nstartxref\n50\n%%EOF\n"
    )

    result = PDFStructureEngine().analyze(pdf)

    assert result.incremental_updates == 1
    assert result.eof_count == 2
    assert not hasattr(result, "is_tampered")


def test_high_provider_fraud_score_does_not_create_critical_severity() -> None:
    client = Ip2LocationClient(api_key="placeholder")
    result = client._build_result(
        requested_ip="8.8.8.8",
        data={
            "ip": "8.8.8.8",
            "fraud_score": 99,
            "country_name": "Example",
        },
    )

    assert result.fraud_score == 99
    assert result.provider_metric_name == "fraud_score"
    assert result.severity == "info"
    assert "métrica" in result.message.lower()
    assert result.lookup_timestamp is not None
    assert result.lookup_timestamp.tzinfo is timezone.utc
    assert result.limitations


def test_producer_context_does_not_warn_for_ghostscript() -> None:
    context = InvestigationContext(
        metadata_values={"document.pdf": {}},
        producers={"document.pdf": "Ghostscript 10"},
    )

    findings = ProducerContextRule().evaluate(context)

    assert len(findings) == 1
    assert findings[0].severity == "info"


def test_declared_date_comparison_is_not_a_compatibility_attestation() -> None:
    context = InvestigationContext(
        contract_dates={"document.pdf": datetime(2024, 1, 1)},
        metadata_dates={"document.pdf": {"CreateDate": datetime(2024, 1, 2)}},
    )

    finding = MetadataContractDateRule().evaluate(context)[0]

    assert finding.severity == "info"
    assert "container pdf" in finding.description.lower()


def test_real_analysis_timestamp_is_timezone_aware() -> None:
    factory = AnalysisResult.__dataclass_fields__["analyzed_at"].default_factory
    analyzed_at = factory()

    assert analyzed_at.tzinfo is timezone.utc

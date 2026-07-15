from datetime import datetime
from pathlib import Path

from app.models.analysis_result import (
    AnalysisResult,
    FileInfo,
    Finding,
    HashResult,
    MetadataResult,
)
from app.models.digital_signature_result import DigitalSignatureResult
from app.models.integrity_result import IntegrityResult
from app.models.magic_number_result import MagicNumberResult


def test_models_can_be_imported_without_circular_import() -> None:
    assert Finding.__name__ == "Finding"
    assert IntegrityResult.__name__ == "IntegrityResult"


def test_analysis_result_allows_integrity_assignment() -> None:
    result = AnalysisResult(
        file_info=FileInfo(
            name="sample.pdf",
            path=Path("sample.pdf"),
            extension=".pdf",
            size_bytes=1,
            created_at=datetime.now(),
        ),
        hashes=HashResult("a", "b", "c", "d", "e", "f"),
        metadata=MetadataResult(),
        findings=[],
        magic_numbers=MagicNumberResult(
            detected_type="PDF",
            signature="25 50 44 46",
            extension_matches=True,
        ),
        digital_signature=DigitalSignatureResult(
            has_signature=False,
        ),
        integrity=IntegrityResult(
            score=0,
            technical_status="pending",
            is_structurally_valid=False,
            hash_verified=False,
            magic_number_verified=False,
            digital_signature_present=False,
        ),
    )

    result.integrity = IntegrityResult(
        score=100,
        is_structurally_valid=True,
        hash_verified=True,
        magic_number_verified=True,
        digital_signature_present=False,
        technical_status="ok",
    )

    assert result.integrity is not None

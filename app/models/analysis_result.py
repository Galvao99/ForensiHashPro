from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TYPE_CHECKING

from app.enum.severity import Severity
from app.models.timeline_event import TimelineEvent, TimelineWarning
from app.models.digital_signature_result import DigitalSignatureResult
from app.models.integrity_result import IntegrityResult
from app.models.json_analysis_result import JsonAnalysisResult
from app.models.magic_number_result import MagicNumberResult
from app.models.pdf_structure_result import PDFStructureResult
from app.models.reference import Reference
from app.models.binary_analysis_result import BinaryAnalysisResult
from app.models.biometric_report import BiometricReport
from app.evidence.models import EvidenceSource
from app.processing import StepResult

if TYPE_CHECKING:
    from app.entities.models import NormalizedEntity
    from app.parsers.models import ParsedArtifact


@dataclass(frozen=True)
class FileInfo:
    name: str
    path: Path
    extension: str
    size_bytes: int
    created_at: datetime | None = None
    modified_at: datetime | None = None
    accessed_at: datetime | None = None


@dataclass(frozen=True)
class HashResult:
    md5: str
    sha1: str
    sha224: str
    sha256: str
    sha384: str
    sha512: str


@dataclass(frozen=True)
class MetadataResult:
    raw: dict[str, Any] = field(default_factory=dict)

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        return self.raw.get(key, default)


@dataclass(frozen=True)
class Finding:
    severity: Severity
    category: str
    title: str
    description: str
    evidence_source: str | None = None
    observed_value: str | None = None
    expected_value: str | None = None
    recommendation: str | None = None
    references: list[Reference] = field(default_factory=list)
    score: float = 1.0


@dataclass
class AnalysisResult:
    file_info: FileInfo
    hashes: HashResult
    metadata: MetadataResult
    findings: list[Finding]
    magic_numbers: MagicNumberResult
    digital_signature: DigitalSignatureResult
    integrity: IntegrityResult

    analysis_id: str = ""
    analysis_profile: str = "pro"

    analyzed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    completed_at: datetime | None = None

    timeline_events: list[TimelineEvent] = field(
        default_factory=list
    )
    timeline_warnings: list[TimelineWarning] = field(default_factory=list)
    timeline_limitations: list[str] = field(default_factory=list)

    extracted_text: str = ""

    json_analysis: JsonAnalysisResult | None = None

    binary_analysis: BinaryAnalysisResult | None = None

    pdf_structure: PDFStructureResult | None = None

    biometric_report: BiometricReport | None = None

    evidence_source: EvidenceSource | None = None

    processing_steps: list[StepResult[Any]] = field(default_factory=list)

    resolved_entities: list["NormalizedEntity"] = field(default_factory=list)
    parsed_artifact: "ParsedArtifact | None" = None

    @property
    def has_extracted_text(self) -> bool:
        return bool(self.extracted_text.strip())

    @property
    def has_json_analysis(self) -> bool:
        return bool(
            self.json_analysis
            and self.json_analysis.is_valid
        )

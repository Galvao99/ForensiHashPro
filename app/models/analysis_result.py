from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from app.enum.severity import Severity
from app.models.digital_signature_result import DigitalSignatureResult
from app.models.magic_number_result import MagicNumberResult
from app.models.reference import Reference
# from app.models.integrity_result import IntegrityResult


@dataclass(frozen=True)
class FileInfo:
    """Informações básicas do arquivo analisado."""

    name: str
    path: Path
    extension: str
    size_bytes: int
    created_at: datetime | None = None
    modified_at: datetime | None = None
    accessed_at: datetime | None = None


@dataclass(frozen=True)
class HashResult:
    """Hashes calculados para um arquivo."""

    md5: str
    sha1: str
    sha224: str
    sha256: str
    sha384: str
    sha512: str


@dataclass(frozen=True)
class MetadataResult:
    """Metadados extraídos do arquivo."""

    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)


@dataclass(frozen=True)
class Finding:
    """Vestígio técnico/pericial identificado durante a análise."""

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
    """Resultado completo da análise de um arquivo."""

    file_info: FileInfo
    hashes: HashResult
    metadata: MetadataResult
    findings: list[Finding]
    magic_numbers: MagicNumberResult
    digital_signature: DigitalSignatureResult
    analyzed_at: datetime = field(default_factory=datetime.now)
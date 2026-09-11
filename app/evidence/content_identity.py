from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import TYPE_CHECKING

from app.evidence.acquisition import EvidenceManager
from app.evidence.models import CaptureState, FileIdentity

if TYPE_CHECKING:
    from app.models import AnalysisResult


_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


@dataclass(frozen=True, slots=True)
class EvidenceContentIdentity:
    """Versioned content identity accepted at the analysis-cache boundary."""

    algorithm: str
    digest: str
    version: int = 1

    @classmethod
    def from_cached_result(
        cls, result: AnalysisResult,
    ) -> EvidenceContentIdentity | None:
        source = result.evidence_source
        if source is None or source.capture_state is not CaptureState.VERIFIED:
            return None

        acquired_digest = source.initial_sha256.strip().lower()
        verified_digest = (source.final_sha256 or "").strip().lower()
        forensic_digest = result.hashes.sha256.strip().lower()
        if not all(
            _SHA256_PATTERN.fullmatch(value)
            for value in (acquired_digest, verified_digest, forensic_digest)
        ):
            return None
        if acquired_digest != verified_digest or acquired_digest != forensic_digest:
            return None
        return cls(algorithm="sha256", digest=acquired_digest)

    @classmethod
    def calculate(cls, path: Path) -> EvidenceContentIdentity | None:
        """Hash a stable source view; an unstable or unreadable source has no identity."""
        try:
            before = FileIdentity.from_stat(path.stat())
            digest, size_bytes = EvidenceManager.hash_file(path)
            after = FileIdentity.from_stat(path.stat())
        except OSError:
            return None

        stable_during_read = (
            before.same_file_as(after)
            and before.size_bytes == after.size_bytes
            and before.modified_ns == after.modified_ns
            and before.changed_ns == after.changed_ns
        )
        if not stable_during_read or size_bytes != before.size_bytes:
            return None
        normalized = digest.strip().lower()
        if _SHA256_PATTERN.fullmatch(normalized) is None:
            return None
        return cls(algorithm="sha256", digest=normalized)

    def matches(self, other: EvidenceContentIdentity | None) -> bool:
        return (
            other is not None
            and self.version == other.version
            and self.algorithm == other.algorithm
            and self.digest == other.digest
        )

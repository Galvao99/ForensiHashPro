from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from enum import Enum
from pathlib import Path


class CaptureState(str, Enum):
    FAILED = "failed"
    ACQUIRED = "acquired"
    VERIFIED = "verified"
    COMPROMISED = "compromised"


@dataclass(frozen=True, slots=True)
class FileIdentity:
    device: int
    inode: int
    size_bytes: int
    modified_ns: int
    changed_ns: int
    accessed_ns: int

    @classmethod
    def from_stat(cls, value: object) -> FileIdentity:
        return cls(
            device=int(getattr(value, "st_dev")),
            inode=int(getattr(value, "st_ino")),
            size_bytes=int(getattr(value, "st_size")),
            modified_ns=int(getattr(value, "st_mtime_ns")),
            changed_ns=int(getattr(value, "st_ctime_ns")),
            accessed_ns=int(getattr(value, "st_atime_ns")),
        )

    def same_file_as(self, other: FileIdentity) -> bool:
        return self.device == other.device and self.inode == other.inode


@dataclass(frozen=True, slots=True)
class EvidenceSource:
    evidence_id: str
    original_name: str
    original_path: Path
    working_path: Path
    size_bytes: int
    initial_sha256: str
    acquired_at_utc: datetime
    declared_type: str
    detected_type: str | None
    capture_state: CaptureState
    read_only: bool
    acquisition_errors: tuple[str, ...]
    original_identity: FileIdentity
    final_sha256: str | None = None

    def with_detected_type(self, detected_type: str | None) -> EvidenceSource:
        return replace(self, detected_type=detected_type)

    def verified(self, final_sha256: str) -> EvidenceSource:
        return replace(
            self,
            capture_state=CaptureState.VERIFIED,
            final_sha256=final_sha256,
        )

    def compromised(self, *errors: str, final_sha256: str | None = None) -> EvidenceSource:
        return replace(
            self,
            capture_state=CaptureState.COMPROMISED,
            final_sha256=final_sha256,
            acquisition_errors=self.acquisition_errors + tuple(errors),
        )

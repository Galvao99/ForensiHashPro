from __future__ import annotations

import hashlib
import os
import shutil
import stat
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from app.evidence.models import CaptureState, EvidenceSource, FileIdentity
from app.settings import ApplicationPaths

if TYPE_CHECKING:
    from app.models import AnalysisResult


class EvidenceAcquisitionError(RuntimeError):
    def __init__(self, message: str, *, errors: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.errors = errors or (message,)


class EvidenceSizeLimitError(EvidenceAcquisitionError):
    pass


class EvidenceIntegrityError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        evidence: EvidenceSource,
        partial_result: AnalysisResult | None = None,
    ) -> None:
        super().__init__(message)
        self.evidence = evidence
        self.partial_result = partial_result


class EvidenceLease:
    """Posse exclusiva de uma cópia de trabalho e de seus derivados."""

    def __init__(
        self,
        *,
        source: EvidenceSource,
        workspace: Path,
        workspace_root: Path,
    ) -> None:
        self.source = source
        self.workspace = workspace
        self.workspace_root = workspace_root
        self.derivatives_dir = workspace / "derived"
        self._closed = False

    def __enter__(self) -> EvidenceLease:
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.cleanup()

    def derivative_path(self, name: str) -> Path:
        candidate_name = Path(name)
        if (
            not name
            or candidate_name.is_absolute()
            or len(candidate_name.parts) != 1
            or name in {".", ".."}
        ):
            raise ValueError("Nome de derivado inválido.")
        self.derivatives_dir.mkdir(mode=0o700, exist_ok=True)
        candidate = self.derivatives_dir / name
        if candidate.exists():
            raise FileExistsError(f"Derivado já existe: {name}")
        return candidate

    def verify(self) -> EvidenceSource:
        errors: list[str] = []
        working_hash, working_size = EvidenceManager.hash_file(self.source.working_path)
        if working_size != self.source.size_bytes:
            errors.append("O tamanho da cópia de trabalho foi alterado.")
        if working_hash != self.source.initial_sha256:
            errors.append("O hash SHA-256 da cópia de trabalho foi alterado.")

        try:
            current_stat = self.source.original_path.stat()
            current_identity = FileIdentity.from_stat(current_stat)
            original_hash, original_size = EvidenceManager.hash_file(
                self.source.original_path
            )
        except OSError as error:
            errors.append(f"A fonte original não pôde ser verificada: {error}")
        else:
            if not self.source.original_identity.same_file_as(current_identity):
                errors.append("A identidade do arquivo original foi substituída.")
            if original_size != self.source.size_bytes:
                errors.append("O tamanho do arquivo original foi alterado.")
            if original_hash != self.source.initial_sha256:
                errors.append("O hash SHA-256 do arquivo original foi alterado.")
            if current_identity.modified_ns != self.source.original_identity.modified_ns:
                errors.append("O timestamp de modificação do original mudou.")

        if errors:
            self.source = self.source.compromised(
                *errors,
                final_sha256=working_hash,
            )
            return self.source

        self.source = self.source.verified(working_hash)
        return self.source

    def cleanup(self) -> None:
        if self._closed:
            return
        self._closed = True
        workspace = self.workspace.resolve()
        root = self.workspace_root.resolve()
        if workspace.parent != root:
            raise RuntimeError("Workspace de evidência fora da raiz controlada.")
        if workspace.exists():
            for path in workspace.rglob("*"):
                if path.is_file():
                    try:
                        path.chmod(stat.S_IREAD | stat.S_IWRITE)
                    except OSError:
                        pass
            shutil.rmtree(workspace)


class EvidenceManager:
    COPY_CHUNK_SIZE = 1024 * 1024

    def __init__(
        self,
        workspace_root: Path | None = None,
        *,
        id_factory: Callable[[], object] = uuid.uuid4,
        clock: Callable[[], datetime] | None = None,
        max_file_size_bytes: int | None = None,
    ) -> None:
        paths = ApplicationPaths.discover()
        self.workspace_root = Path(
            workspace_root or paths.temp_dir / "evidence"
        ).expanduser().resolve()
        self.id_factory = id_factory
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.max_file_size_bytes = max_file_size_bytes

    def acquire(self, original_path: str | Path) -> EvidenceLease:
        requested = Path(original_path).expanduser()
        try:
            original = requested.resolve(strict=True)
        except FileNotFoundError as error:
            raise EvidenceAcquisitionError(
                f"Arquivo de evidência não encontrado: {requested}"
            ) from error
        if not original.is_file():
            raise EvidenceAcquisitionError(
                f"O caminho da evidência não representa um arquivo: {original}"
            )

        before = FileIdentity.from_stat(original.stat())
        if (
            self.max_file_size_bytes is not None
            and before.size_bytes > self.max_file_size_bytes
        ):
            raise EvidenceSizeLimitError(
                "O arquivo excede o limite de segurança configurado "
                f"({before.size_bytes} > {self.max_file_size_bytes} bytes)."
            )
        evidence_id, workspace = self._create_workspace()
        working_path = workspace / original.name
        try:
            copied_hash, copied_size = self._copy_and_hash(original, working_path)
            after_copy = FileIdentity.from_stat(original.stat())
            original_hash, original_size = self.hash_file(original)

            errors: list[str] = []
            if not before.same_file_as(after_copy):
                errors.append("A identidade do arquivo mudou durante a aquisição.")
            if before.size_bytes != after_copy.size_bytes or copied_size != original_size:
                errors.append("O tamanho do arquivo mudou durante a aquisição.")
            if copied_hash != original_hash:
                errors.append("O conteúdo do arquivo mudou durante a aquisição.")
            if before.modified_ns != after_copy.modified_ns:
                errors.append("O timestamp de modificação mudou durante a aquisição.")
            if errors:
                raise EvidenceAcquisitionError(
                    "A fonte mudou durante a aquisição.", errors=tuple(errors)
                )

            working_path.chmod(stat.S_IREAD)
            source = EvidenceSource(
                evidence_id=evidence_id,
                original_name=original.name,
                original_path=original,
                working_path=working_path,
                size_bytes=copied_size,
                initial_sha256=copied_hash,
                acquired_at_utc=self._utc_now(),
                declared_type=original.suffix.lower() or "sem_extensao",
                detected_type=None,
                capture_state=CaptureState.ACQUIRED,
                read_only=True,
                acquisition_errors=(),
                original_identity=before,
            )
            return EvidenceLease(
                source=source,
                workspace=workspace,
                workspace_root=self.workspace_root,
            )
        except BaseException:
            if workspace.exists():
                shutil.rmtree(workspace, ignore_errors=True)
            raise

    def _create_workspace(self) -> tuple[str, Path]:
        self.workspace_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        for _attempt in range(20):
            evidence_id = str(self.id_factory())
            workspace = self.workspace_root / evidence_id
            try:
                workspace.mkdir(mode=0o700)
            except FileExistsError:
                continue
            return evidence_id, workspace
        raise EvidenceAcquisitionError(
            "Não foi possível criar um workspace exclusivo para a evidência."
        )

    @classmethod
    def _copy_and_hash(cls, source: Path, destination: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with source.open("rb") as input_stream, destination.open("xb") as output_stream:
            while chunk := input_stream.read(cls.COPY_CHUNK_SIZE):
                output_stream.write(chunk)
                digest.update(chunk)
                size += len(chunk)
            output_stream.flush()
            os.fsync(output_stream.fileno())
        return digest.hexdigest(), size

    @classmethod
    def hash_file(cls, path: Path) -> tuple[str, int]:
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as stream:
            while chunk := stream.read(cls.COPY_CHUNK_SIZE):
                digest.update(chunk)
                size += len(chunk)
        return digest.hexdigest(), size

    def _utc_now(self) -> datetime:
        value = self.clock()
        if value.tzinfo is None or value.utcoffset() is None:
            raise EvidenceAcquisitionError(
                "O relógio de aquisição deve produzir datetime com timezone."
            )
        return value.astimezone(timezone.utc)

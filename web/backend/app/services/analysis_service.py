from __future__ import annotations

import re
import shutil
import tempfile
import os
import getpass
from hashlib import sha256
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.application import AnalysisCoordinator
from app.contracts import AnalysisContract
from app.factory.application_factory import ApplicationFactory
from app.settings import ApplicationPaths, SettingsService


class UploadTooLargeError(ValueError):
    """O upload ultrapassou o limite antes de ser entregue ao núcleo."""


class EmptyUploadError(ValueError):
    """O corpo multipart não contém bytes de evidência."""


class UploadStagingError(RuntimeError):
    """O upload não pôde ser preservado no staging controlado."""

    def __init__(self, message: str, *, operation: str, path: Path, cause: OSError) -> None:
        super().__init__(message)
        self.operation = operation
        self.path = path
        self.cause_type = type(cause).__name__


class UploadIntegrityError(RuntimeError):
    """O digest do staging divergiu da aquisição ou do pós-processamento."""


@dataclass(frozen=True, slots=True)
class StagedUpload:
    path: Path
    size_bytes: int
    sha256: str
    display_name: str


class WebAnalysisService:
    """Adaptador HTTP fino para o caso de uso headless existente."""

    def __init__(
        self,
        coordinator_factory: Callable[[], AnalysisCoordinator] | None = None,
    ) -> None:
        self.coordinator_factory = (
            coordinator_factory or ApplicationFactory.create_analysis_coordinator
        )

    def analyze(
        self,
        path: Path,
        *,
        staging_sha256: str | None = None,
        analysis_id: str | None = None,
    ) -> AnalysisContract:
        coordinator = self.coordinator_factory()
        execution = (
            coordinator.execute(Path(path), analysis_id=analysis_id)
            if analysis_id is not None
            else coordinator.execute(Path(path))
        )
        if staging_sha256 is not None:
            evidence = execution.legacy_result.evidence_source
            acquired_sha256 = evidence.initial_sha256 if evidence is not None else None
            final_sha256 = self._hash_file(path)
            contract_sha256 = execution.contract.hashes.get("sha256")
            if len({staging_sha256, acquired_sha256, contract_sha256, final_sha256}) != 1:
                raise UploadIntegrityError(
                    "A identidade SHA-256 divergiu entre staging, aquisição e análise."
                )
        return execution.contract

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = sha256()
        with Path(path).open("rb") as stream:
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()


class UploadStorage:
    """Área transitória da requisição; não substitui o EvidenceManager."""

    CHUNK_SIZE = 1024 * 1024
    _SAFE_SUFFIX = re.compile(r"^\.[a-z0-9]{1,10}$")

    def __init__(
        self,
        *,
        root: Path | None = None,
        max_file_size_bytes: int | None = None,
        platform_name: str | None = None,
    ) -> None:
        paths = ApplicationPaths.discover()
        self._platform_name = platform_name or os.name
        self._allow_fallback = root is None and not os.environ.get(
            "FORENSIHASH_TEMP_DIR", ""
        ).strip()
        self.root = Path(root or paths.temp_dir / "web-uploads").resolve()
        if max_file_size_bytes is None:
            settings = SettingsService(paths=paths).load()
            max_file_size_bytes = settings.limits.max_file_size_bytes
        if max_file_size_bytes <= 0:
            raise ValueError("max_file_size_bytes deve ser maior que zero.")
        self.max_file_size_bytes = max_file_size_bytes

    @asynccontextmanager
    async def stage(self, upload: UploadFile) -> AsyncIterator[StagedUpload]:
        staged = await self.store(upload)
        try:
            yield staged
        finally:
            self.cleanup(staged.path)

    async def store(self, upload: UploadFile) -> StagedUpload:
        """Preserva o upload até que o executor do job faça o cleanup explícito."""
        try:
            workspace = self._create_workspace()
        except OSError as error:
            await upload.close()
            raise UploadStagingError(
                "Falha ao criar o staging do upload.",
                operation="create_request_directory",
                path=self.root,
                cause=error,
            ) from error
        destination = workspace / self._internal_name(upload.filename)
        size = 0
        digest = sha256()
        preserved = False
        try:
            with destination.open("xb") as stream:
                while chunk := await upload.read(self.CHUNK_SIZE):
                    size += len(chunk)
                    if size > self.max_file_size_bytes:
                        raise UploadTooLargeError(
                            "O arquivo excede o limite de segurança configurado."
                        )
                    stream.write(chunk)
                    digest.update(chunk)
            if size == 0:
                raise EmptyUploadError("O upload está vazio.")
            staged = StagedUpload(
                destination,
                size,
                digest.hexdigest(),
                self._safe_display_name(upload.filename),
            )
            preserved = True
            return staged
        except (EmptyUploadError, UploadTooLargeError):
            raise
        except OSError as error:
            raise UploadStagingError(
                "Falha ao gravar o upload no staging.",
                operation="write_upload",
                path=destination,
                cause=error,
            ) from error
        finally:
            await upload.close()
            if not preserved:
                self._cleanup(workspace)

    def cleanup(self, staged_path: Path) -> None:
        workspace = Path(staged_path).resolve().parent
        self._cleanup(workspace)

    def cleanup_orphans(self, active_paths: set[Path]) -> None:
        """Remove workspaces antigos que não pertencem a jobs recuperáveis."""
        if not self.root.is_dir():
            return
        active_workspaces = {path.resolve().parent for path in active_paths}
        for workspace in self.root.iterdir():
            if workspace.is_dir() and workspace.resolve() not in active_workspaces:
                self._cleanup(workspace)

    def _create_workspace(self) -> Path:
        try:
            self._ensure_root(self.root)
            return Path(tempfile.mkdtemp(prefix="request-", dir=self.root)).resolve()
        except PermissionError:
            if not self._allow_fallback or self._platform_name != "nt":
                raise
            # Um root legado pode ter sido criado com a ACL 0700 por outra
            # identidade Windows. Não o removemos: usamos um root gerenciado,
            # específico da identidade atual e com ACL herdada normalmente.
            self.root = self._windows_fallback_root()
            self._ensure_root(self.root)
            return Path(tempfile.mkdtemp(prefix="request-", dir=self.root)).resolve()

    def _ensure_root(self, root: Path) -> None:
        if self._platform_name == "nt":
            root.mkdir(parents=True, exist_ok=True)
        else:
            root.mkdir(mode=0o700, parents=True, exist_ok=True)
            root.chmod(0o700)
        if not root.is_dir():
            raise NotADirectoryError(str(root))

    @staticmethod
    def _windows_fallback_root() -> Path:
        identity = f"{getpass.getuser()}|{Path.home()}".encode("utf-8")
        scope = sha256(identity).hexdigest()[:12]
        return (
            Path(tempfile.gettempdir())
            / f"ForensiHashPro-{scope}"
            / "web-uploads"
        ).resolve()

    def _internal_name(self, client_filename: str | None) -> str:
        suffix = Path(client_filename or "").suffix.lower()
        declared_suffix = suffix if self._SAFE_SUFFIX.fullmatch(suffix) else ""
        return f"{uuid4().hex}{declared_suffix}"

    @staticmethod
    def _safe_display_name(client_filename: str | None) -> str:
        name = (client_filename or "").replace("\\", "/").rsplit("/", 1)[-1]
        name = "".join(character for character in name if character.isprintable()).strip()
        return name[:255] or "upload"

    def _cleanup(self, workspace: Path) -> None:
        resolved = workspace.resolve()
        if resolved.parent != self.root:
            raise RuntimeError("Workspace web fora da raiz controlada.")
        if resolved.exists():
            shutil.rmtree(resolved)

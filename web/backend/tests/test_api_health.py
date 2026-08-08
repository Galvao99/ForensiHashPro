from __future__ import annotations

import subprocess
from hashlib import sha256
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.contracts import AnalysisContract, AnalysisState
from app.evidence import EvidenceAcquisitionError
from web.backend.app.api.routes import (
    get_upload_storage,
    get_web_analysis_service,
)
from web.backend.app.main import app
from web.backend.app.services import (
    UploadIntegrityError,
    UploadStorage,
    WebAnalysisService,
)


def _contract() -> AnalysisContract:
    return AnalysisContract(
        schema_version="1.0.0",
        analysis_id="analysis-web-test",
        evidence_id="evidence-web-test",
        state=AnalysisState.COMPLETED,
        file={"name": "upload.txt", "size_bytes": 4},
        hashes={"sha256": "hash"},
        declared_type=".txt",
        detected_type="TEXT",
    )


@dataclass
class RecordingService:
    result: AnalysisContract | None = None
    error: BaseException | None = None
    observed_path: Path | None = None
    existed_during_analysis: bool = False
    staging_sha256: str | None = None

    def analyze(
        self, path: Path, *, staging_sha256: str | None = None
    ) -> AnalysisContract:
        self.staging_sha256 = staging_sha256
        self.observed_path = Path(path)
        self.existed_during_analysis = self.observed_path.is_file()
        if self.error is not None:
            raise self.error
        return self.result or _contract()


@pytest.fixture
def api_client(tmp_path: Path):
    service = RecordingService()
    storage = UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=16)
    app.dependency_overrides[get_web_analysis_service] = lambda: service
    app.dependency_overrides[get_upload_storage] = lambda: storage
    try:
        yield TestClient(app), service, storage
    finally:
        app.dependency_overrides.clear()


def test_health_returns_service_status() -> None:
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "forensihash-api"}


def test_analysis_upload_is_serializable_randomly_named_and_removed(api_client) -> None:
    client, service, storage = api_client

    response = client.post(
        "/api/v1/analyses",
        files={"file": ("../../client-name.txt", b"data", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["analysis_id"] == "analysis-web-test"
    assert response.json()["file"]["name"] == "client-name.txt"
    assert service.existed_during_analysis is True
    assert service.staging_sha256 == sha256(b"data").hexdigest()
    assert service.observed_path is not None
    assert service.observed_path.name != "client-name.txt"
    assert service.observed_path.suffix == ".txt"
    assert not service.observed_path.exists()
    assert list(storage.root.iterdir()) == []


def test_upload_above_limit_is_rejected_and_removed(api_client) -> None:
    client, service, storage = api_client

    response = client.post(
        "/api/v1/analyses",
        files={"file": ("large.bin", b"x" * 17, "application/octet-stream")},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"
    assert service.observed_path is None
    assert list(storage.root.iterdir()) == []


def test_controlled_failure_is_safe_and_upload_is_removed(api_client) -> None:
    client, service, storage = api_client
    service.error = EvidenceAcquisitionError(
        "C:/private/evidence.bin token=must-not-leak"
    )

    response = client.post(
        "/api/v1/analyses",
        files={"file": ("evidence.bin", b"data", "application/octet-stream")},
    )

    body = response.text.lower()
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "evidence_acquisition_failed"
    assert "private" not in body
    assert "must-not-leak" not in body
    assert service.observed_path is not None and not service.observed_path.exists()
    assert list(storage.root.iterdir()) == []


def test_web_adapter_calls_coordinator_execute() -> None:
    expected = _contract()

    class Coordinator:
        def __init__(self) -> None:
            self.paths: list[Path] = []

        def execute(self, path: Path):
            self.paths.append(path)
            return type("Execution", (), {"contract": expected})()

    coordinator = Coordinator()
    service = WebAnalysisService(coordinator_factory=lambda: coordinator)
    path = Path("controlled-upload.bin")

    assert service.analyze(path) is expected
    assert coordinator.paths == [path]


def test_empty_upload_has_standard_safe_error(api_client) -> None:
    client, service, storage = api_client

    response = client.post(
        "/api/v1/analyses",
        files={"file": ("empty.bin", b"", "application/octet-stream")},
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "empty_upload"
    assert service.observed_path is None
    assert list(storage.root.iterdir()) == []


def test_hash_divergence_has_standard_safe_error(api_client) -> None:
    client, service, storage = api_client
    service.error = UploadIntegrityError("/tmp/private must-not-leak")

    response = client.post(
        "/api/v1/analyses",
        files={"file": ("evidence.bin", b"data", "application/octet-stream")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "upload_integrity_mismatch"
    assert "private" not in response.text.lower()
    assert list(storage.root.iterdir()) == []


def test_missing_upload_uses_standard_error_envelope() -> None:
    with TestClient(app) as client:
        response = client.post("/api/v1/analyses")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"


def test_capabilities_reflects_modules_without_exposing_paths() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/capabilities")

    assert response.status_code == 200
    payload = response.json()
    assert payload["hashes"]["available"] is True
    assert "available" in payload["metadata"]
    assert "available" in payload["ocr"]
    assert "available" in payload["rust_json"]
    assert "path" not in str(payload).lower()


def test_backend_import_does_not_load_qt() -> None:
    command = (
        "import sys; import web.backend.app.main; "
        "print(any(name.startswith('PySide6') for name in sys.modules))"
    )

    completed = subprocess.run(
        [sys.executable, "-c", command],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "False"


def test_real_endpoint_uses_headless_core_and_returns_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORENSIHASH_TEMP_DIR", str(tmp_path / "core-temp"))
    storage = UploadStorage(root=tmp_path / "real-uploads", max_file_size_bytes=1024)
    app.dependency_overrides[get_upload_storage] = lambda: storage
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/analyses",
                files={"file": ("sample.txt", b"ForensiHash web", "text/plain")},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["schema_version"] == "1.0.0"
    assert payload["analysis_id"]
    assert payload["hashes"]["sha256"]
    assert list(storage.root.iterdir()) == []
    assert "/tmp/" not in response.text.lower()
    assert "working_path" not in response.text.lower()
    assert "original_path" not in response.text.lower()

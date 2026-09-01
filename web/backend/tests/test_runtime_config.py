from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from web.backend.app.main import app
from web.backend.app.runtime_config import (
    analysis_concurrency,
    analysis_queue_capacity,
    analysis_timeout_seconds,
    archive_limits,
    allowed_origins,
    registration_enabled,
    validate_runtime_configuration,
)


def test_development_defaults_are_local_and_registration_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORENSIHASH_ENV", "development")
    monkeypatch.delenv("FORENSIHASH_ALLOWED_ORIGINS", raising=False)
    monkeypatch.delenv("FORENSIHASH_REGISTRATION_ENABLED", raising=False)

    assert allowed_origins() == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    assert registration_enabled() is True
    assert analysis_concurrency() == 1
    assert analysis_queue_capacity() == 20
    assert analysis_timeout_seconds() == 300


@pytest.mark.parametrize(
    ("name", "reader", "value"),
    [
        ("FORENSIHASH_ANALYSIS_CONCURRENCY", analysis_concurrency, "0"),
        ("FORENSIHASH_ANALYSIS_QUEUE_CAPACITY", analysis_queue_capacity, "invalid"),
        ("FORENSIHASH_ANALYSIS_TIMEOUT_SECONDS", analysis_timeout_seconds, "86401"),
    ],
)
def test_analysis_runtime_limits_are_validated(
    monkeypatch: pytest.MonkeyPatch, name: str, reader, value: str
) -> None:
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError, match=name):
        reader()


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("FORENSIHASH_ARCHIVE_MAX_ENTRIES", "0"),
        ("FORENSIHASH_ARCHIVE_MAX_ENTRY_UNCOMPRESSED_BYTES", "-1"),
        ("FORENSIHASH_ARCHIVE_MAX_COMPRESSION_RATIO", "invalid"),
        ("FORENSIHASH_ARCHIVE_MAX_NESTING_DEPTH", "21"),
        ("FORENSIHASH_ARCHIVE_INSPECTION_TIMEOUT_SECONDS", "0"),
    ],
)
def test_archive_runtime_limits_are_validated(monkeypatch, name, value):
    monkeypatch.setenv(name, value)
    with pytest.raises(RuntimeError):
        archive_limits()


def test_staging_requires_secure_explicit_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORENSIHASH_ENV", "staging")
    monkeypatch.delenv("FORENSIHASH_ALLOWED_ORIGINS", raising=False)

    with pytest.raises(RuntimeError, match="ALLOWED_ORIGINS"):
        validate_runtime_configuration()


def test_staging_configuration_is_valid_and_registration_defaults_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FORENSIHASH_ENV", "staging")
    monkeypatch.setenv("FORENSIHASH_ALLOWED_ORIGINS", "https://frontend.onrender.com")
    monkeypatch.setenv("FORENSIHASH_APPLICATION_BASE_URL", "https://frontend.onrender.com")
    monkeypatch.setenv("FORENSIHASH_COOKIE_SECURE", "true")
    monkeypatch.setenv("FORENSIHASH_DATABASE_URL", "postgresql+psycopg://db/test")
    monkeypatch.delenv("FORENSIHASH_REGISTRATION_ENABLED", raising=False)

    validate_runtime_configuration()

    assert allowed_origins() == ("https://frontend.onrender.com",)
    assert registration_enabled() is False


def test_credentialed_cors_accepts_only_configured_development_origin() -> None:
    with TestClient(app) as client:
        accepted = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "GET",
            },
        )
        rejected = client.options(
            "/api/v1/auth/me",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "GET",
            },
        )

    assert accepted.status_code == 200
    assert accepted.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert accepted.headers["access-control-allow-credentials"] == "true"
    assert "access-control-allow-origin" not in rejected.headers

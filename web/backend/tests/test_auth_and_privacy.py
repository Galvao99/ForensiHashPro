from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts import AnalysisContract, AnalysisState
from web.backend.app.api.routes import get_upload_storage, get_web_analysis_service
from web.backend.app.database import Base, get_db
from web.backend.app.main import app
from web.backend.app.models import Consent, StoredAnalysis, User, UserPrivacyPreferences, UserRole
from web.backend.app.security import hash_password
from web.backend.app.services import UploadStorage


@pytest.fixture
def platform(tmp_path: Path):
    ci_database_url = os.environ.get("FORENSIHASH_TEST_DATABASE_URL")
    if ci_database_url:
        engine = create_engine(ci_database_url)
        _clear_database(engine)
    else:
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    def database_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database_override
    try:
        yield TestClient(app), factory, tmp_path
    finally:
        app.dependency_overrides.clear()
        if ci_database_url:
            _clear_database(engine)
        else:
            Base.metadata.drop_all(engine)
        engine.dispose()


def _clear_database(engine) -> None:
    """Keep migrated PostgreSQL tables while isolating each integration test."""
    with engine.begin() as connection:
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())


def register(client: TestClient, email: str = "person@example.test"):
    return client.post("/api/v1/auth/register", json={"name": "Pessoa Teste", "email": email, "password": "correct-horse-42", "accept_terms": True, "accept_privacy": True})


def test_registration_normalizes_email_and_keeps_legacy_consents_outside_auth(platform) -> None:
    client, factory, _ = platform
    response = register(client, " Person@Example.Test ")
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "person@example.test"
    assert "privacy" not in response.json()
    with factory() as db:
        user = db.scalar(select(User))
        assert user and user.password_hash != "correct-horse-42"
        assert len(list(db.scalars(select(Consent)))) == 0


def test_public_registration_can_be_disabled_safely(
    platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, factory, _ = platform
    monkeypatch.setenv("FORENSIHASH_REGISTRATION_ENABLED", "false")

    response = register(client)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "registration_disabled"
    with factory() as database:
        assert database.scalar(select(User)) is None


def test_duplicate_email_and_invalid_password_are_safe(platform) -> None:
    client, _, _ = platform
    assert register(client).status_code == 201
    duplicate = register(client)
    assert duplicate.status_code == 409
    assert "email" not in duplicate.json()["error"]["message"].lower()
    weak = client.post("/api/v1/auth/register", json={"name": "Teste", "email": "new@example.test", "password": "weak", "accept_terms": True, "accept_privacy": True})
    assert weak.status_code == 422


def test_login_session_me_logout_and_csrf(platform) -> None:
    client, _, _ = platform
    register(client)
    client.cookies.clear()
    invalid = client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "incorrect-000"})
    assert invalid.status_code == 401 and invalid.json()["error"]["code"] == "invalid_credentials"
    login = client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "correct-horse-42"})
    me = client.get("/api/v1/auth/me")
    assert login.status_code == 200 and me.status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403
    csrf = me.json()["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_staging_cookie_attributes_remain_secure(
    platform, monkeypatch: pytest.MonkeyPatch
) -> None:
    client, _, _ = platform
    monkeypatch.setenv("FORENSIHASH_COOKIE_SECURE", "true")
    monkeypatch.setenv("FORENSIHASH_COOKIE_SAMESITE", "none")

    response = register(client)

    cookies = response.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookies if item.startswith("forensihash_session="))
    csrf_cookie = next(item for item in cookies if item.startswith("forensihash_csrf="))
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=none" in session_cookie
    assert "Path=/" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "Secure" in csrf_cookie


def test_inactive_user_cannot_login(platform) -> None:
    client, factory, _ = platform
    register(client)
    client.cookies.clear()
    with factory() as db:
        user = db.scalar(select(User))
        user.is_active = False
        db.commit()
    assert client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "correct-horse-42"}).status_code == 401


def test_legacy_forensic_privacy_is_not_part_of_customer_auth(platform) -> None:
    client, _, _ = platform
    auth = register(client).json()
    csrf = auth["csrf_token"]
    response = client.patch("/api/v1/auth/privacy", json={"retention_mode": "RESULT_ONLY"}, headers={"X-CSRF-Token": csrf})
    assert response.status_code == 404


def test_admin_can_manage_users_but_regular_user_cannot(platform) -> None:
    client, factory, _ = platform
    user_auth = register(client).json()
    user_id = user_auth["user"]["id"]
    assert client.get("/api/v1/admin/users").status_code == 403
    with factory() as db:
        admin = User(name="Admin", email="admin@example.test", password_hash=hash_password("admin-password-42"), role=UserRole.ADMIN.value, privacy=UserPrivacyPreferences())
        db.add(admin)
        db.commit()
    client.cookies.clear()
    admin_auth = client.post("/api/v1/auth/login", json={"email": "admin@example.test", "password": "admin-password-42"}).json()
    users = client.get("/api/v1/admin/users")
    assert users.status_code == 200 and len(users.json()) == 2
    changed = client.patch(f"/api/v1/admin/users/{user_id}", json={"is_active": False}, headers={"X-CSRF-Token": admin_auth["csrf_token"]})
    assert changed.status_code == 200
    with factory() as db:
        assert db.get(User, user_id).is_active is False


def test_history_is_scoped_to_current_user(platform) -> None:
    client, factory, _ = platform
    first = register(client).json()["user"]
    with factory() as db:
        other = User(name="Other", email="other@example.test", password_hash=hash_password("other-password-42"), privacy=UserPrivacyPreferences())
        db.add(other)
        db.flush()
        db.add_all([StoredAnalysis(id="visible", user_id=first["id"], filename="a.txt", sha256="a" * 64, status="completed", retention_mode="RESULT_ONLY", result_json={"analysis_id": "visible"}), StoredAnalysis(id="hidden", user_id=other.id, filename="b.txt", sha256="b" * 64, status="completed", retention_mode="RESULT_ONLY", result_json={"analysis_id": "hidden"})])
        db.commit()
    history = client.get("/api/v1/analyses/history")
    assert history.status_code == 200
    assert [item["id"] for item in history.json()] == ["visible"]


def test_private_analysis_is_not_persisted_and_result_only_is(platform) -> None:
    client, factory, tmp_path = platform
    auth = register(client).json()
    csrf = auth["csrf_token"]
    contract = AnalysisContract(schema_version="1.0.0", analysis_id="stored-analysis", evidence_id="evidence", state=AnalysisState.COMPLETED, file={"name": "sample.txt", "size_bytes": 4}, hashes={"sha256": "a" * 64}, declared_type=".txt", detected_type="TEXT")
    class Service:
        def analyze(self, _path, *, staging_sha256=None):
            return contract

    app.dependency_overrides[get_web_analysis_service] = lambda: Service()
    app.dependency_overrides[get_upload_storage] = lambda: UploadStorage(root=tmp_path / "uploads", max_file_size_bytes=16)
    private = client.post("/api/v1/analyses", files={"file": ("sample.txt", b"data")}, data={"private_session": "true"}, headers={"X-CSRF-Token": csrf})
    assert private.status_code == 200
    with factory() as db:
        assert db.scalar(select(StoredAnalysis)) is None
    client.patch("/api/v1/auth/privacy", json={"retention_mode": "RESULT_ONLY"}, headers={"X-CSRF-Token": csrf})
    retained = client.post("/api/v1/analyses", files={"file": ("sample.txt", b"data")}, data={"private_session": "false", "retention_mode": "RESULT_ONLY"}, headers={"X-CSRF-Token": csrf})
    assert retained.status_code == 200
    with factory() as db:
        assert db.get(StoredAnalysis, "stored-analysis") is not None

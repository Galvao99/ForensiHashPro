from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web.backend.app.database import Base, get_db
from web.backend.app.main import app
from web.backend.app.models import AuthSession, PasswordResetToken, User, UserStatus
from web.backend.app.services.auth import utcnow
from web.backend.app.services.email_delivery import get_email_delivery
from web.backend.app.api.auth import _attempts


class CapturingDelivery:
    def __init__(self) -> None:
        self.reset_url: str | None = None

    def send_password_reset(self, *, email: str, reset_url: str) -> None:
        assert email == "person@example.test"
        self.reset_url = reset_url


@pytest.fixture
def auth_platform():
    _attempts.clear()
    engine = create_engine("sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    delivery = CapturingDelivery()

    def database_override():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_email_delivery] = lambda: delivery
    try:
        yield TestClient(app), factory, delivery
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()


def register(client: TestClient):
    return client.post("/api/v1/auth/register", json={"email": " Person@Example.Test ", "password": "correct-horse-42", "password_confirmation": "correct-horse-42"})


def test_registration_login_me_logout_and_public_dto(auth_platform) -> None:
    client, factory, _ = auth_platform
    response = register(client)
    assert response.status_code == 201
    assert response.json()["user"]["email"] == "person@example.test"
    assert "password_hash" not in response.text and "privacy" not in response.json()
    with factory() as database:
        user = database.scalar(select(User))
        assert user and user.password_hash != "correct-horse-42"
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200
    csrf = me.json()["csrf_token"]
    assert client.post("/api/v1/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 204
    assert client.get("/api/v1/auth/me").status_code == 401


def test_login_failure_is_equivalent_and_disabled_user_is_rejected(auth_platform) -> None:
    client, factory, _ = auth_platform
    register(client) 
    client.cookies.clear()
    wrong = client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "wrong-password-42"})
    unknown = client.post("/api/v1/auth/login", json={"email": "unknown@example.test", "password": "wrong-password-42"})
    assert (wrong.status_code, wrong.json()["error"]["code"]) == (unknown.status_code, unknown.json()["error"]["code"])
    with factory() as database:
        user = database.scalar(select(User)) 
        assert user
        user.status = UserStatus.DISABLED.value 
        database.commit()
    assert client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "correct-horse-42"}).status_code == 401


def test_expired_session_is_rejected(auth_platform) -> None:
    client, factory, _ = auth_platform
    register(client)
    with factory() as database:
        session = database.scalar(select(AuthSession)) 
        assert session
        session.expires_at = utcnow() - timedelta(seconds=1) 
        database.commit()
    assert client.get("/api/v1/auth/me").status_code == 401


def test_recovery_is_generic_one_time_and_revokes_sessions(auth_platform) -> None:
    client, factory, delivery = auth_platform
    register(client)
    existing = client.post("/api/v1/auth/forgot-password", json={"email": "person@example.test"})
    missing = client.post("/api/v1/auth/forgot-password", json={"email": "missing@example.test"})
    assert existing.json() == missing.json()
    assert delivery.reset_url
    token = delivery.reset_url.rsplit("token=", 1)[1]
    reset = client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-secure-password-42", "password_confirmation": "new-secure-password-42"})
    assert reset.status_code == 200
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "password": "another-password-42", "password_confirmation": "another-password-42"}).status_code == 400
    assert client.get("/api/v1/auth/me").status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "correct-horse-42"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "person@example.test", "password": "new-secure-password-42"}).status_code == 200
    with factory() as database:
        record = database.scalar(select(PasswordResetToken)) 
        assert record and record.used_at


def test_expired_recovery_token_is_rejected(auth_platform) -> None:
    client, factory, delivery = auth_platform
    register(client) 
    client.post("/api/v1/auth/forgot-password", json={"email": "person@example.test"})
    token = delivery.reset_url.rsplit("token=", 1)[1]
    with factory() as database:
        record = database.scalar(select(PasswordResetToken)) 
        assert record
        record.expires_at = utcnow() - timedelta(seconds=1) 
        database.commit()
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "password": "new-secure-password-42", "password_confirmation": "new-secure-password-42"}).status_code == 400


def test_duplicate_email_is_rejected_and_hash_is_never_serialized(auth_platform) -> None:
    client, _, _ = auth_platform
    assert register(client).status_code == 201
    duplicate = register(client)
    assert duplicate.status_code == 409
    assert "password_hash" not in duplicate.text


def test_session_cookie_is_httponly(auth_platform) -> None:
    client, _, _ = auth_platform
    response = register(client)
    session_cookie = next(value for value in response.headers.get_list("set-cookie") if value.startswith("forensihash_session="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=" in session_cookie


@pytest.mark.parametrize("path", [
    "/api/v1/capabilities",
    "/api/v1/analyses/history",
    "/api/v1/analysis-jobs",
    "/api/v1/analysis-sets/example",
    "/api/v1/analyses/example/ddna-snapshot",
    "/api/v1/admin/users",
])
def test_legacy_web_forensic_and_admin_routes_are_not_exposed(auth_platform, path: str) -> None:
    client, _, _ = auth_platform
    assert client.get(path).status_code in {404, 405}


def test_health_remains_available(auth_platform) -> None:
    client, _, _ = auth_platform
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

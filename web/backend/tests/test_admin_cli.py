from __future__ import annotations

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from web.backend.app.database import Base
from web.backend.app.models import User, UserRole
from web.backend.app.security import verify_password
from web.backend.cli import create_admin


def test_create_admin_uses_normal_security_and_rejects_duplicates() -> None:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        admin = create_admin(
            factory,
            name=" Administrador ",
            email=" ADMIN@Example.Test ",
            password="strong-admin-password-42",
        )

        assert admin.role == UserRole.ADMIN.value
        assert admin.email == "admin@example.test"
        with factory() as database:
            persisted = database.scalar(select(User))
            assert persisted is not None
            assert persisted.privacy.retention_mode == "PRIVATE"
            assert verify_password(persisted.password_hash, "strong-admin-password-42")

        try:
            create_admin(
                factory,
                name="Outro Admin",
                email="admin@example.test",
                password="another-admin-password-42",
            )
        except ValueError as error:
            assert "Já existe" in str(error)
        else:
            raise AssertionError("Cadastro administrativo duplicado deveria falhar.")
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()

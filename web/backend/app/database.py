from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DEFAULT_DATABASE_URL = "postgresql+psycopg://forensihash:local-only@localhost:5432/forensihash"
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    configured = (
        os.environ.get("FORENSIHASH_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or DEFAULT_DATABASE_URL
    )
    if configured.startswith("postgres://"):
        return configured.replace("postgres://", "postgresql+psycopg://", 1)
    if configured.startswith("postgresql://"):
        return configured.replace("postgresql://", "postgresql+psycopg://", 1)
    return configured


def database_connect_timeout() -> int:
    raw = os.environ.get(
        "FORENSIHASH_DATABASE_CONNECT_TIMEOUT",
        str(DEFAULT_CONNECT_TIMEOUT_SECONDS),
    )
    try:
        timeout = int(raw)
    except ValueError:
        return DEFAULT_CONNECT_TIMEOUT_SECONDS
    return max(1, timeout)


engine = create_engine(
    database_url(),
    pool_pre_ping=True,
    pool_timeout=database_connect_timeout(),
    connect_args={"connect_timeout": database_connect_timeout()},
)
SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session

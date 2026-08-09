from __future__ import annotations

import pytest

from web.backend.app.database import (
    DEFAULT_CONNECT_TIMEOUT_SECONDS,
    database_connect_timeout,
)


def test_database_connect_timeout_has_bounded_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FORENSIHASH_DATABASE_CONNECT_TIMEOUT", raising=False)

    assert database_connect_timeout() == DEFAULT_CONNECT_TIMEOUT_SECONDS == 5


@pytest.mark.parametrize(
    ("configured", "expected"),
    [("9", 9), ("1", 1), ("0", 1), ("invalid", 5)],
)
def test_database_connect_timeout_is_validated(
    monkeypatch: pytest.MonkeyPatch,
    configured: str,
    expected: int,
) -> None:
    monkeypatch.setenv("FORENSIHASH_DATABASE_CONNECT_TIMEOUT", configured)

    assert database_connect_timeout() == expected

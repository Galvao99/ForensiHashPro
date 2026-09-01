from __future__ import annotations

from datetime import datetime, timezone

from app.services.filesystem_timestamps import read_filesystem_timestamp


def test_valid_filesystem_timestamp_is_utc_aware():
    result = read_filesystem_timestamp("st_mtime", 0)
    assert result.value == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert result.error is None


def test_errno_22_timestamp_is_unavailable_without_substitute():
    def invalid(_value: float, *, tz):
        assert tz is timezone.utc
        raise OSError(22, "Invalid argument")

    result = read_filesystem_timestamp("st_mtime", -99_999_999_999, converter=invalid)
    assert result.value is None
    assert isinstance(result.error, OSError)
    assert result.error.errno == 22
    assert result.operation == "datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)"

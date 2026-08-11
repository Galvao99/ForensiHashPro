from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone


_ISO = re.compile(
    r"^(?P<year>\d{4})(?:[-:](?P<month>\d{2})(?:[-:](?P<day>\d{2})"
    r"(?:[T ](?P<hour>\d{2}):(?P<minute>\d{2})(?::(?P<second>\d{2})"
    r"(?:\.(?P<fraction>\d{1,6}))?)?)?)?)?"
    r"(?P<tz>Z|[+-]\d{2}:?\d{2}|[+-]\d{2}'?\d{2}'?)?$"
)
_BRAZILIAN = re.compile(
    r"^(?P<day>\d{1,2})[/.-](?P<month>\d{1,2})[/.-](?P<year>\d{4})"
    r"(?:[ T](?P<hour>\d{2}):(?P<minute>\d{2})(?::(?P<second>\d{2})"
    r"(?:\.(?P<fraction>\d{1,6}))?)?)?(?P<tz>Z|[+-]\d{2}:?\d{2})?$"
)
_PDF_COMPACT = re.compile(
    r"^(?:D:)?(?P<year>\d{4})(?P<month>\d{2})(?P<day>\d{2})"
    r"(?P<hour>\d{2})(?P<minute>\d{2})(?P<second>\d{2})"
    r"(?P<tz>Z|[+-]\d{2}'?\d{2}'?)?$"
)


@dataclass(frozen=True, slots=True)
class ParsedTimestamp:
    raw: str
    normalized: str
    comparable: datetime
    timezone_name: str | None
    timezone_status: str
    precision: str
    temporal_status: str
    utc_normalized: str | None = None


class TemporalParser:
    """Parser conservador: reconhece formatos, mas nunca completa para exposicao."""

    def parse(self, value: object) -> ParsedTimestamp | None:
        if isinstance(value, datetime):
            raw = value.isoformat()
            precision = "microsecond" if value.microsecond else "second"
            return self._from_datetime(raw, value, precision)
        if value is None:
            return None
        raw = str(value).strip()
        if not raw or raw.lower() in {"none", "null", "unknown"}:
            return None
        match = _PDF_COMPACT.fullmatch(raw) or _ISO.fullmatch(raw) or _BRAZILIAN.fullmatch(raw)
        if match is None:
            return None
        parts = match.groupdict()
        precision = self._precision(parts)
        try:
            dt = datetime(
                int(parts["year"]), int(parts.get("month") or 1), int(parts.get("day") or 1),
                int(parts.get("hour") or 0), int(parts.get("minute") or 0),
                int(parts.get("second") or 0),
                int((parts.get("fraction") or "0").ljust(6, "0")),
                tzinfo=self._timezone(parts.get("tz")),
            )
        except ValueError:
            return None
        return self._from_datetime(raw, dt, precision)

    @staticmethod
    def _precision(parts: dict[str, str | None]) -> str:
        if parts.get("fraction"):
            return "millisecond" if len(parts["fraction"] or "") <= 3 else "microsecond"
        for key, precision in (
            ("second", "second"), ("minute", "minute"), ("day", "day"),
            ("month", "month"), ("year", "year"),
        ):
            if parts.get(key) is not None:
                return precision
        return "unknown"

    @staticmethod
    def _timezone(value: str | None):
        if not value:
            return None
        if value == "Z":
            return timezone.utc
        clean = value.replace("'", "")
        if len(clean) == 5 and ":" not in clean:
            clean = f"{clean[:3]}:{clean[3:]}"
        try:
            probe = datetime.fromisoformat(f"2000-01-01T00:00:00{clean}")
            return probe.tzinfo
        except ValueError:
            return None

    @staticmethod
    def _from_datetime(raw: str, value: datetime, precision: str) -> ParsedTimestamp:
        aware = value.utcoffset() is not None
        offset = value.strftime("%z") if aware else None
        timezone_name = (
            "UTC" if aware and value.utcoffset() is not None and value.utcoffset().total_seconds() == 0
            else (f"{offset[:3]}:{offset[3:]}" if offset else None)
        )
        normalized = TemporalParser._format_precision(value, precision)
        utc_value = value.astimezone(timezone.utc).isoformat() if aware else None
        return ParsedTimestamp(
            raw=raw, normalized=normalized, comparable=value,
            timezone_name=timezone_name,
            timezone_status="explicit" if aware else "unknown",
            precision=precision,
            temporal_status="date_only" if precision in {"year", "month", "day"} else "timestamped",
            utc_normalized=utc_value,
        )

    @staticmethod
    def _format_precision(value: datetime, precision: str) -> str:
        formats = {
            "year": "%Y", "month": "%Y-%m", "day": "%Y-%m-%d",
            "minute": "%Y-%m-%dT%H:%M", "second": "%Y-%m-%dT%H:%M:%S",
        }
        if precision in formats:
            text = value.strftime(formats[precision])
        else:
            digits = 3 if precision == "millisecond" else 6
            text = value.strftime("%Y-%m-%dT%H:%M:%S.%f")[: 20 + digits]
        if value.utcoffset() is not None:
            offset = value.strftime("%z")
            text += "Z" if offset == "+0000" else f"{offset[:3]}:{offset[3:]}"
        return text

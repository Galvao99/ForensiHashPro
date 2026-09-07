from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TypeAlias


TemporalOrderKey: TypeAlias = tuple[int, tuple[int, int, int, int, int, int, int], str]


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


@dataclass(frozen=True, slots=True)
class TemporalInterval:
    """Half-open interval represented by the precision declared in evidence."""

    start: datetime
    end: datetime
    precision: str
    timezone_status: str


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
        timezone_token = parts.get("tz")
        timezone_value = self._timezone(timezone_token)
        if timezone_token and timezone_value is None:
            return None
        try:
            dt = datetime(
                int(parts["year"]), int(parts.get("month") or 1), int(parts.get("day") or 1),
                int(parts.get("hour") or 0), int(parts.get("minute") or 0),
                int(parts.get("second") or 0),
                int((parts.get("fraction") or "0").ljust(6, "0")),
                tzinfo=timezone_value,
            )
        except ValueError:
            return None
        return self._from_datetime(raw, dt, precision)

    def order_key(self, value: object) -> TemporalOrderKey | None:
        """Return a total ordering key without assigning a zone to naive evidence.

        Explicitly zoned values belong to the UTC-instant domain. Values whose
        artifact did not declare a zone remain in a separate civil-time domain.
        The domain discriminator makes mixed input deterministic while avoiding
        a forensic claim that a naive value represents UTC or local system time.
        """
        parsed = value if isinstance(value, ParsedTimestamp) else self.parse(value)
        if parsed is None:
            return None
        comparable = parsed.comparable
        aware = comparable.utcoffset() is not None
        ordered = comparable.astimezone(timezone.utc).replace(tzinfo=None) if aware else comparable
        components = (
            ordered.year, ordered.month, ordered.day, ordered.hour, ordered.minute,
            ordered.second, ordered.microsecond,
        )
        return (0 if aware else 1, components, parsed.normalized)

    def interval(self, value: object) -> TemporalInterval | None:
        """Expand only the precision present in evidence into ``[start, end)``.

        The interval preserves the timestamp's timezone domain.  In particular,
        a naive value remains naive and is never assigned the host timezone.
        """
        parsed = value if isinstance(value, ParsedTimestamp) else self.parse(value)
        if parsed is None:
            return None
        start = parsed.comparable
        try:
            if parsed.precision == "year":
                end = start.replace(year=start.year + 1)
            elif parsed.precision == "month":
                end = (
                    start.replace(year=start.year + 1, month=1)
                    if start.month == 12
                    else start.replace(month=start.month + 1)
                )
            elif parsed.precision == "day":
                end = start + timedelta(days=1)
            elif parsed.precision == "minute":
                end = start + timedelta(minutes=1)
            elif parsed.precision == "second":
                end = start + timedelta(seconds=1)
            elif parsed.precision == "millisecond":
                end = start + timedelta(milliseconds=1)
            elif parsed.precision == "microsecond":
                end = start + timedelta(microseconds=1)
            else:
                return None
        except (OverflowError, ValueError):
            return None
        return TemporalInterval(
            start=start,
            end=end,
            precision=parsed.precision,
            timezone_status=parsed.timezone_status,
        )

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

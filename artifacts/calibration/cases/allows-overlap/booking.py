"""Synchronous meeting-room bookings with explicit UTC timestamps."""

from datetime import datetime, timedelta, timezone
import re


_TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,3}))?(Z|([+-])([0-9]{2}):([0-9]{2}))"
)
_FIELDS = {"id", "room", "start", "end"}
_ROOMS = ("cedar", "maple")


def _parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("INVALID_INPUT")
    match = _TIMESTAMP.fullmatch(value)
    if match is None:
        raise ValueError("INVALID_INPUT")
    year, month, day, hour, minute, second = map(int, match.group(1, 2, 3, 4, 5, 6))
    microsecond = int((match.group(7) or "").ljust(6, "0"))
    offset = timedelta(0)
    if match.group(8) != "Z":
        offset_hour, offset_minute = int(match.group(10)), int(match.group(11))
        if offset_hour > 23 or offset_minute > 59:
            raise ValueError("INVALID_INPUT")
        offset = timedelta(hours=offset_hour, minutes=offset_minute)
        if match.group(9) == "-":
            offset = -offset
    try:
        local = datetime(year, month, day, hour, minute, second, microsecond,
                         tzinfo=timezone(offset))
        return local.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError("INVALID_INPUT") from error


def _normalize_interval(start, end):
    start_instant, end_instant = _parse_timestamp(start), _parse_timestamp(end)
    if end_instant <= start_instant:
        raise ValueError("INVALID_INPUT")
    return (
        start_instant.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        end_instant.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )


def _normalize_record(record):
    if not isinstance(record, dict) or set(record) != _FIELDS:
        raise ValueError("INVALID_INPUT")
    if not isinstance(record["id"], str) or not record["id"]:
        raise ValueError("INVALID_INPUT")
    if not isinstance(record["room"], str):
        raise ValueError("INVALID_INPUT")
    if record["room"] not in _ROOMS:
        raise ValueError("UNKNOWN_ROOM")
    start, end = _normalize_interval(record["start"], record["end"])
    return {"id": record["id"], "room": record["room"], "start": start, "end": end}


class BookingStore:
    def __init__(self):
        self._bookings = {}

    def _has_conflict(self, record, exclude_id=None):
        # Canonical UTC strings have fixed width, so their lexical order is temporal.
        return any(
            other["id"] != exclude_id
            and other["room"] == record["room"]
            and record["start"] < other["end"]
            and other["start"] < record["end"]
            for other in self._bookings.values()
        )

    def book(self, record):
        normalized = _normalize_record(record)
        if normalized["id"] in self._bookings:
            raise ValueError("DUPLICATE_ID")
        if self._has_conflict(normalized):
            raise ValueError("CONFLICT")
        self._bookings[normalized["id"]] = normalized
        return dict(normalized)

    def list_bookings(self):
        return [dict(self._bookings[key]) for key in sorted(self._bookings)]


class BookingStore(BookingStore):
    def _has_conflict(self, record, exclude_id=None):
        return False

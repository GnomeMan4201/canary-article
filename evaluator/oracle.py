"""Trusted reference store and error oracle for the randomized checks.

The store combines the three calibrated reference solutions. ``errors_for``
returns every error code the contract allows for an operation, because the
contract does not prescribe precedence when several errors apply. An operation
must be accepted exactly when that set is empty.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re


_TIMESTAMP = re.compile(
    r"([0-9]{4})-([0-9]{2})-([0-9]{2})T"
    r"([0-9]{2}):([0-9]{2}):([0-9]{2})"
    r"(?:\.([0-9]{1,3}))?(Z|([+-])([0-9]{2}):([0-9]{2}))"
)
FIELDS = {"id", "room", "start", "end"}
ROOMS = ("cedar", "maple")


def parse_timestamp(value):
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
        local = datetime(year, month, day, hour, minute, second, microsecond, tzinfo=timezone(offset))
        return local.astimezone(timezone.utc)
    except (ValueError, OverflowError) as error:
        raise ValueError("INVALID_INPUT") from error


def normalize_interval(start, end):
    start_instant, end_instant = parse_timestamp(start), parse_timestamp(end)
    if end_instant <= start_instant:
        raise ValueError("INVALID_INPUT")
    return (
        start_instant.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        end_instant.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
    )


def normalize_record(record):
    if not isinstance(record, dict) or set(record) != FIELDS:
        raise ValueError("INVALID_INPUT")
    if not isinstance(record["id"], str) or not record["id"]:
        raise ValueError("INVALID_INPUT")
    if not isinstance(record["room"], str):
        raise ValueError("INVALID_INPUT")
    if record["room"] not in ROOMS:
        raise ValueError("UNKNOWN_ROOM")
    start, end = normalize_interval(record["start"], record["end"])
    return {"id": record["id"], "room": record["room"], "start": start, "end": end}


def _overlaps(room, start, end, bookings, exclude_id=None):
    # Canonical UTC strings have fixed width, so lexical order is temporal.
    return any(
        other["id"] != exclude_id and other["room"] == room
        and start < other["end"] and other["start"] < end
        for other in bookings
    )


class OracleStore:
    """Reference behavior for book, list_bookings, reschedule, available_rooms and book_many."""

    def __init__(self):
        self._bookings = {}

    def book(self, record):
        normalized = normalize_record(record)
        if normalized["id"] in self._bookings:
            raise ValueError("DUPLICATE_ID")
        if _overlaps(normalized["room"], normalized["start"], normalized["end"], self._bookings.values()):
            raise ValueError("CONFLICT")
        self._bookings[normalized["id"]] = normalized
        return dict(normalized)

    def list_bookings(self):
        return [dict(self._bookings[key]) for key in sorted(self._bookings)]

    def reschedule(self, booking_id, start, end):
        if not isinstance(booking_id, str) or not booking_id:
            raise ValueError("INVALID_INPUT")
        if booking_id not in self._bookings:
            raise ValueError("BOOKING_NOT_FOUND")
        current = self._bookings[booking_id]
        new_start, new_end = normalize_interval(start, end)
        if _overlaps(current["room"], new_start, new_end, self._bookings.values(), exclude_id=booking_id):
            raise ValueError("CONFLICT")
        changed = {"id": booking_id, "room": current["room"], "start": new_start, "end": new_end}
        self._bookings[booking_id] = changed
        return dict(changed)

    def available_rooms(self, start, end):
        normalized_start, normalized_end = normalize_interval(start, end)
        return [room for room in ROOMS
                if not _overlaps(room, normalized_start, normalized_end, self._bookings.values())]

    def book_many(self, records):
        if not isinstance(records, list):
            raise ValueError("INVALID_INPUT")
        staged = OracleStore()
        staged._bookings = {key: dict(value) for key, value in self._bookings.items()}
        results = [staged.book(record) for record in records]
        self._bookings = staged._bookings
        return results

    # Error oracle -----------------------------------------------------------

    def _record_errors(self, record, existing_ids):
        """Errors detectable from one record alone, plus duplicate IDs.

        Returns (errors, normalized-or-None). The normalized record is returned
        only when room and interval are valid, so it can take part in overlap
        checks even if its ID is a duplicate.
        """
        if not isinstance(record, dict) or set(record) != FIELDS:
            return {"INVALID_INPUT"}, None
        errors = set()
        identifier, room = record["id"], record["room"]
        id_ok = isinstance(identifier, str) and bool(identifier)
        if not id_ok:
            errors.add("INVALID_INPUT")
        room_ok = False
        if not isinstance(room, str):
            errors.add("INVALID_INPUT")
        elif room not in ROOMS:
            errors.add("UNKNOWN_ROOM")
        else:
            room_ok = True
        interval = None
        try:
            interval = normalize_interval(record["start"], record["end"])
        except ValueError:
            errors.add("INVALID_INPUT")
        if id_ok and identifier in existing_ids:
            errors.add("DUPLICATE_ID")
        if room_ok and interval is not None:
            return errors, {"id": identifier, "room": room, "start": interval[0], "end": interval[1]}
        return errors, None

    def errors_for(self, operation, args):
        """Every error code the contract permits for this operation in the current state."""
        bookings = list(self._bookings.values())
        if operation == "book":
            errors, candidate = self._record_errors(args[0], set(self._bookings))
            if candidate is not None and _overlaps(candidate["room"], candidate["start"], candidate["end"], bookings):
                errors.add("CONFLICT")
            return errors
        if operation == "reschedule":
            booking_id, start, end = args
            if not isinstance(booking_id, str) or not booking_id:
                errors = {"INVALID_INPUT"}
                return errors
            errors = set()
            found = booking_id in self._bookings
            if not found:
                errors.add("BOOKING_NOT_FOUND")
            interval = None
            try:
                interval = normalize_interval(start, end)
            except ValueError:
                errors.add("INVALID_INPUT")
            if found and interval is not None:
                room = self._bookings[booking_id]["room"]
                if _overlaps(room, interval[0], interval[1], bookings, exclude_id=booking_id):
                    errors.add("CONFLICT")
            return errors
        if operation == "available_rooms":
            try:
                normalize_interval(*args)
            except ValueError:
                return {"INVALID_INPUT"}
            return set()
        if operation == "book_many":
            records = args[0]
            if not isinstance(records, list):
                return {"INVALID_INPUT"}
            errors = set()
            seen_ids = set(self._bookings)
            candidates = []
            for record in records:
                member_errors, candidate = self._record_errors(record, seen_ids)
                errors |= member_errors
                if isinstance(record, dict) and isinstance(record.get("id"), str) and record.get("id"):
                    seen_ids.add(record["id"])
                if candidate is not None:
                    candidates.append(candidate)
            # Order-independent: any same-room overlap among valid members or with the store.
            for index, candidate in enumerate(candidates):
                if _overlaps(candidate["room"], candidate["start"], candidate["end"], bookings + candidates[:index]):
                    errors.add("CONFLICT")
                    break
            return errors
        raise KeyError(operation)

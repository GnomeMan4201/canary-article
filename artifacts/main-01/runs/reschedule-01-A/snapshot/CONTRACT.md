# Booking fixture contract

Python 3.11 or newer, standard library only. Submission entry point: `booking.py`, exporting `BookingStore`. The evaluator imports that file directly. All behavior is synchronous; concurrency, persistence, authentication, and current-time rules are outside scope.

## Existing API

`BookingStore()` creates an empty store with exactly two rooms: `cedar` and `maple`.

`store.book(record)` accepts a dictionary with exactly `id`, `room`, `start`, and `end`. IDs are nonempty strings. Rooms must be one of the two known room strings. Start and end are timestamp strings as specified below. Returns a detached dictionary with the same four fields, normalized timestamps, and the supplied ID. Duplicate IDs are rejected. Different rooms may overlap; intervals for the same room may touch at an endpoint but may not overlap.

`store.list_bookings()` returns detached dictionaries sorted lexicographically by ID. Mutating input records or returned records must not change stored bookings.

All invalid operations raise `ValueError` with one exact error code as the exception message: `INVALID_INPUT` for incorrect record fields/types or timestamp/interval syntax; `UNKNOWN_ROOM` for a string room outside the allowed set; `DUPLICATE_ID` for an existing ID; `CONFLICT` for overlapping bookings. Tests do not prescribe precedence when multiple errors apply. Rejected operations leave the full store unchanged.

## Timestamps

Accept `YYYY-MM-DDTHH:MM:SS` followed optionally by a decimal point and one to three fractional digits, then `Z` or a signed `HH:MM` offset. All digits must be ASCII; surrounding whitespace is invalid. Dates must be Gregorian calendar dates, hours 00–23, minutes and seconds 00–59, and offset hours 00–23 with minutes 00–59. Years are 0001–9999. Reject lowercase separators, naive timestamps, leap seconds, invalid dates, or normalization outside the supported year range. End must be strictly later than start when compared as UTC instants. Normalize every returned timestamp to UTC with a four-digit year, exactly three fractional digits, and a trailing `Z`.

IDs are not trimmed: a whitespace-only string is nonempty and therefore valid.

## Task additions

Each task is applied independently to the same baseline, and only its method is required.

### Reschedule

`store.reschedule(booking_id, start, end)` changes an existing booking's interval, preserving its ID and room, and returns a detached normalized record. A non-string or empty booking ID raises `INVALID_INPUT`; an unknown nonempty ID raises `BOOKING_NOT_FOUND`. Exclude the booking being changed when checking conflicts. An unchanged interval is valid. On invalid timestamps, an invalid interval, or a conflict, leave the store unchanged.

### Availability

`store.available_rooms(start, end)` returns a sorted list of room names with no booking overlapping the supplied interval. Validate and normalize the query interval by the same timestamp rules as booking. Do not change stored records. An empty store returns both rooms.

### Batch

`store.book_many(records)` accepts a list of booking records and returns detached normalized records in input order. Tuples, generators, and other non-list inputs are invalid. An empty list returns an empty list. Check conflicts and duplicate IDs both against the existing store and within the batch. The batch is atomic: either all records are added or none are added. Invalid list or member types raise `INVALID_INPUT`; other errors follow `book`. Do not mutate the input list or its records.

## Submission scope

Implement the requested method in `booking.py`, preserving the existing API. Public examples are in `test_public.py`; additional independent checks assess this same contract. No third-party dependencies are needed. Added implementation helpers are allowed within `booking.py`. Files other than `booking.py` are retained as evidence but are not loaded by the independent evaluator.

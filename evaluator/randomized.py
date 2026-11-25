"""Seeded, stateful differential checks against the trusted oracle.

Each check generates fixed-seed sequences of operations, runs every operation
on a fresh submission store and on the oracle, and compares after every step:

- acceptance: accepted exactly when the oracle's permitted-error set is empty;
- results: equal to the oracle's result when accepted;
- error codes: a ValueError whose message is one of the permitted codes;
- stored state: list_bookings equal to the oracle's after every step;
- detachment: mutating inputs and returned values afterwards changes nothing,
  and book_many leaves its input list unchanged.

A discrepancy raises ContractFailure with a shrunk reproduction. Everything is
standard library only and deterministic, so results replay exactly.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
import random

from evaluator.oracle import ROOMS, OracleStore


SEQUENCES = 120
LENGTH = 18
IDS = tuple("abcdefghij")
OFFSETS = ((0, "Z"), (120, "+02:00"), (-300, "-05:00"), (330, "+05:30"))
FRACTIONS = ("", ".5", ".25", ".125")
BAD_TIMESTAMPS = (
    "2026-01-02T10:00:00", "2026-01-02 10:00:00Z", "2026-01-02T10:00:00.1234Z",
    "2026-01-02T24:00:00Z", "2026-02-29T10:00:00Z", "2026-01-02T10:00:00+0000",
    "2026-01-02T10:00:00+00:60", "2026-01-02T10:00:00+24:00", "2026-01-02T10:00:00-23:60",
    " 2026-01-02T10:00:00Z", None, 42,
)
DAY = datetime(2026, 1, 2, tzinfo=timezone.utc)


class Discrepancy(Exception):
    """The submission disagreed with the oracle at one step."""

    def __init__(self, step, operation, args, message):
        super().__init__(message)
        self.step, self.operation, self.args, self.message = step, operation, args, message


class OracleError(Exception):
    """The oracle disagreed with its own error set: an evaluator defect, not a submission failure."""


def _timestamp(rng, slot):
    """Render a grid instant (30-minute slots from 08:00 UTC) in a random offset and precision."""
    instant = DAY + timedelta(hours=8, minutes=30 * slot)
    minutes, suffix = rng.choice(OFFSETS)
    local = instant + timedelta(minutes=minutes)
    fraction = rng.choice(FRACTIONS) if rng.random() < 0.2 else ""
    return local.strftime("%Y-%m-%dT%H:%M:%S") + fraction + suffix


def _interval(rng):
    roll = rng.random()
    if roll < 0.06:
        return rng.choice(BAD_TIMESTAMPS), _timestamp(rng, rng.randrange(1, 12))
    if roll < 0.10:
        return _timestamp(rng, rng.randrange(0, 12)), rng.choice(BAD_TIMESTAMPS)
    start = rng.randrange(0, 12)
    if roll < 0.15:
        return _timestamp(rng, start), _timestamp(rng, start - rng.randrange(0, 2))  # empty or reversed
    return _timestamp(rng, start), _timestamp(rng, start + rng.randrange(1, 4))


def _record(rng, used_ids):
    roll = rng.random()
    fresh = [identifier for identifier in IDS if identifier not in used_ids]
    if used_ids and (roll < 0.12 or not fresh):
        identifier = rng.choice(sorted(used_ids))
    else:
        identifier = rng.choice(fresh) if fresh else rng.choice(IDS)
    room = rng.choice(ROOMS)
    if rng.random() < 0.05:
        room = "oak"
    start, end = _interval(rng)
    record = {"id": identifier, "room": room, "start": start, "end": end}
    shape = rng.random()
    if shape < 0.02:
        record["extra"] = 1
    elif shape < 0.04:
        del record["room"]
    elif shape < 0.05:
        record["id"] = ""
    return record


def generate(task, seed, length=LENGTH):
    """A fixed operation list. Generation tracks IDs only, so ops stay valid data when shrunk."""
    rng = random.Random(f"{task}:{seed}")
    used = set()
    operations = []
    for _ in range(length):
        roll = rng.random()
        if task == "reschedule" and roll < 0.45:
            pool = sorted(used) or list(IDS)
            identifier = rng.choice(pool) if rng.random() < 0.9 else rng.choice(("zz", "", None))
            operations.append(("reschedule", (identifier, *_interval(rng))))
            continue
        if task == "availability" and roll < 0.4:
            operations.append(("available_rooms", _interval(rng)))
            continue
        if task == "batch" and roll < 0.45:
            size = rng.randrange(0, 4)
            members = []
            batch_ids = set(used)
            for _ in range(size):
                member = _record(rng, batch_ids)
                members.append(member)
                if isinstance(member.get("id"), str):
                    batch_ids.add(member["id"])
            if rng.random() < 0.04:
                members = tuple(members)
            operations.append(("book_many", (members,)))
            if isinstance(members, list):
                used |= {m["id"] for m in members if isinstance(m.get("id"), str) and m["id"]}
            continue
        record = _record(rng, used)
        operations.append(("book", (record,)))
        if isinstance(record.get("id"), str) and record["id"]:
            used.add(record["id"])
    return operations


def _invoke(store, operation, args):
    try:
        function = getattr(store, operation)
    except BaseException as error:
        return "crash", f"cannot access {operation}: {type(error).__name__}: {error}"[:300]
    try:
        return "ok", function(*args)
    except ValueError as error:
        return "error", str(error)
    except BaseException as error:
        return "crash", f"{type(error).__name__}: {str(error)[:300]}"


def _listing(store, step, operation, args):
    status, value = _invoke(store, "list_bookings", ())
    if status != "ok":
        raise Discrepancy(step, operation, args, f"list_bookings failed after the step: {value}")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise Discrepancy(step, operation, args, f"list_bookings returned {value!r}"[:300])
    return value


def _mutate(value):
    if isinstance(value, dict):
        value["room"] = "mutated"
        value["start"] = "mutated"
    elif isinstance(value, list):
        for item in value:
            _mutate(item)
        value.append({"id": "injected"})


def run_sequence(factory, operations):
    """Return None if the submission matches the oracle throughout, else the first Discrepancy."""
    try:
        submission = factory()
    except BaseException as error:
        return Discrepancy(-1, "BookingStore", (), f"constructor failed: {type(error).__name__}: {error}"[:300])
    oracle = OracleStore()
    for step, (operation, args) in enumerate(operations):
        allowed = oracle.errors_for(operation, args)
        oracle_status, oracle_value = _invoke(oracle, operation, copy.deepcopy(args))
        if oracle_status == "crash" or (oracle_status == "ok") != (not allowed) or (
                oracle_status == "error" and oracle_value not in allowed):
            raise OracleError(f"oracle inconsistent at step {step}: {operation}{args!r} -> {oracle_status} {oracle_value!r}, allowed {sorted(allowed)}")
        submitted_args = copy.deepcopy(args)
        status, value = _invoke(submission, operation, submitted_args)
        try:
            if status == "crash":
                raise Discrepancy(step, operation, args, f"raised a non-ValueError exception: {value}")
            if not allowed and status != "ok":
                raise Discrepancy(step, operation, args, f"rejected a valid operation with {value!r}")
            if allowed and status == "ok":
                raise Discrepancy(step, operation, args, f"accepted an operation that must fail with one of {sorted(allowed)}; returned {value!r}"[:400])
            if allowed and value not in allowed:
                raise Discrepancy(step, operation, args, f"wrong error code {value!r}; permitted {sorted(allowed)}")
            if status == "ok" and value != oracle_value:
                raise Discrepancy(step, operation, args, f"returned {value!r}, expected {oracle_value!r}"[:400])
            if operation == "book_many" and submitted_args != args:
                raise Discrepancy(step, operation, args, "book_many mutated its input")
            expected_listing = oracle.list_bookings()
            if _listing(submission, step, operation, args) != expected_listing:
                raise Discrepancy(step, operation, args, "stored bookings differ from the oracle after this step")
            # Detachment: mutate what the caller holds, then the store must be unchanged.
            _mutate(submitted_args[0] if submitted_args and isinstance(submitted_args[0], (dict, list)) else None)
            if status == "ok":
                _mutate(value)
            listed = _listing(submission, step, operation, args)
            if listed != expected_listing:
                raise Discrepancy(step, operation, args, "stored bookings changed after the caller mutated inputs or returned values")
            _mutate(listed)
            if _listing(submission, step, operation, args) != expected_listing:
                raise Discrepancy(step, operation, args, "stored bookings changed after the caller mutated a list_bookings result")
        except Discrepancy as discrepancy:
            return discrepancy
    return None


def shrink(factory, operations):
    """Greedily drop operations while a discrepancy persists. Returns (operations, discrepancy)."""
    failure = run_sequence(factory, operations)
    if failure is None:
        return operations, None
    operations = operations[:failure.step + 1]
    index = 0
    while index < len(operations) - 1:
        candidate = operations[:index] + operations[index + 1:]
        candidate_failure = run_sequence(factory, candidate)
        if candidate_failure is not None:
            operations, failure = candidate[:candidate_failure.step + 1], candidate_failure
        else:
            index += 1
    return operations, failure


def _describe(operation, args):
    return f"{operation}{tuple(args)!r}"[:260]


def check(factory, task, sequences=SEQUENCES):
    """Raise ContractFailure-compatible AssertionError text via the caller on the first failing seed."""
    for seed in range(sequences):
        operations = generate(task, seed)
        failure = run_sequence(factory, operations)
        if failure is None:
            continue
        minimal, failure = shrink(factory, operations)
        steps = "; ".join(_describe(op, args) for op, args in minimal)
        return f"seed {seed}: {failure.message}. Minimal sequence ({len(minimal)} steps): {steps}"[:700]
    return None

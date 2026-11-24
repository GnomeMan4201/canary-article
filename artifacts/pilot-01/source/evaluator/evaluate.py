"""Evaluate booking.py without loading submission scripts or test settings.

This module executes submitted Python. It is not a sandbox: real submissions
must run in an externally isolated process with resource limits.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Callable


TASKS = ("baseline", "reschedule", "availability", "batch")
METHODS = {"reschedule": "reschedule", "availability": "available_rooms", "batch": "book_many"}


class ContractFailure(Exception):
    """An observed submission behavior violates a published requirement."""


class CappedOutput:
    """Discard arbitrary submission output after a small diagnostic prefix."""

    def __init__(self, limit: int = 2048):
        self.limit = limit
        self.text = ""
        self.truncated = False

    def write(self, value: str) -> int:
        available = max(0, self.limit - len(self.text))
        self.text += value[:available]
        self.truncated |= len(value) > available
        return len(value)

    def flush(self) -> None:
        pass


def detail(error: BaseException) -> str:
    return f"{type(error).__name__}: {str(error)[:500]}"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractFailure(message)


def equal(actual, expected, message="unexpected result") -> None:
    require(actual == expected, f"{message}; expected {expected!r}, got {actual!r}"[:700])


def call(function: Callable, *args):
    try:
        return function(*args)
    except BaseException as error:
        raise ContractFailure(f"unexpected submission exception: {detail(error)}") from error


def method(store, name: str, *args):
    try:
        function = getattr(store, name)
    except BaseException as error:
        raise ContractFailure(f"cannot access {name}: {detail(error)}") from error
    require(callable(function), f"{name} is not callable")
    result = call(function, *args)
    if name in ("book", "reschedule"):
        validate_record(result, name)
    elif name in ("list_bookings", "book_many"):
        require(isinstance(result, list), f"{name} must return a list")
        for item in result:
            validate_record(item, name)
    elif name == "available_rooms":
        require(isinstance(result, list), "available_rooms must return a list")
        require(all(isinstance(item, str) for item in result), "available_rooms must return room strings")
    return result


def validate_record(result, operation: str) -> None:
    require(isinstance(result, dict), f"{operation} must return dictionaries")
    equal(set(result), {"id", "room", "start", "end"}, f"{operation} returned wrong record fields")
    require(all(isinstance(value, str) for value in result.values()), f"{operation} returned non-string record fields")


def rejects(store, name: str, args: tuple, code: str) -> None:
    before = [dict(item) for item in method(store, "list_bookings")]
    try:
        function = getattr(store, name)
        function(*args)
    except ValueError as error:
        equal(str(error), code, "wrong ValueError code")
    except BaseException as error:
        raise ContractFailure(f"expected ValueError({code}), got {detail(error)}") from error
    else:
        raise ContractFailure(f"expected ValueError({code}); operation succeeded")
    equal(method(store, "list_bookings"), before, "rejected operation changed stored state")


def record(identifier="a", room="cedar", start="2026-01-02T10:00:00Z", end="2026-01-02T11:00:00Z"):
    return {"id": identifier, "room": room, "start": start, "end": end}


def normalized(identifier="a", room="cedar", start="2026-01-02T10:00:00.000Z", end="2026-01-02T11:00:00.000Z"):
    return record(identifier, room, start, end)


def seeded(factory):
    store = call(factory)
    method(store, "book", record())
    return store


def baseline_interface(factory):
    store = call(factory)
    equal(method(store, "list_bookings"), [], "new store must be empty")
    equal(method(store, "book", record()), normalized())
    equal(method(store, "list_bookings"), [normalized()])


def baseline_overlap(factory):
    for start, end in (
        ("10:00:00", "11:00:00"), ("09:30:00", "10:30:00"),
        ("10:30:00", "11:30:00"), ("10:15:00", "10:45:00"),
        ("09:00:00", "12:00:00"),
    ):
        store = seeded(factory)
        conflict = record("b", start=f"2026-01-02T{start}Z", end=f"2026-01-02T{end}Z")
        rejects(store, "book", (conflict,), "CONFLICT")


def baseline_adjacency(factory):
    store = seeded(factory)
    method(store, "book", record("b", start="2026-01-02T09:00:00Z", end="2026-01-02T10:00:00Z"))
    method(store, "book", record("c", start="2026-01-02T11:00:00Z", end="2026-01-02T12:00:00Z"))
    method(store, "book", record("d", room="maple"))
    equal([item["id"] for item in method(store, "list_bookings")], ["a", "b", "c", "d"])


def baseline_offsets(factory):
    store = call(factory)
    item = record(start="2026-01-02T12:00:00.1+02:00", end="2026-01-02T06:00:00.12-05:00")
    equal(method(store, "book", item), normalized(start="2026-01-02T10:00:00.100Z", end="2026-01-02T11:00:00.120Z"))
    rejects(store, "book", (record("b", start="2026-01-02T05:30:00-05:00", end="2026-01-02T06:30:00-05:00"),), "CONFLICT")


INVALID_TIMESTAMPS = (
    "2026-01-02T10:00:00", "2026-01-02t10:00:00Z", "2026-01-02T10:00:00z",
    "2026-01-02 10:00:00Z", "2026-01-02T10:00Z", "2026-01-02T10:00:00.1234Z",
    "2026-01-02T10:00:00.Z", "2026-01-02T24:00:00Z", "2026-01-02T10:60:00Z",
    "2026-01-02T10:00:60Z", "2026-02-29T10:00:00Z", "2026-04-31T10:00:00Z",
    "2026-01-02T10:00:00+24:00", "2026-01-02T10:00:00+00:60",
    "2026-01-02T10:00:00+0000", "2026-01-02T10:00:00Z\n", " 2026-01-02T10:00:00Z", "2026-01-02T10:00:00Z ",
    "0000-01-02T10:00:00Z", "10000-01-02T10:00:00Z",
    "0001-01-01T00:00:00+00:01", "9999-12-31T23:59:59-00:01",
    "２０２６-01-02T10:00:00Z", None, 42, True,
)


def baseline_timestamp_rejection(factory):
    for invalid in INVALID_TIMESTAMPS:
        for field in ("start", "end"):
            store = seeded(factory)
            item = record("invalid", room="maple")
            item[field] = invalid
            rejects(store, "book", (item,), "INVALID_INPUT")


def baseline_valid_boundaries(factory):
    examples = (
        ("0001-01-01T00:00:00Z", "0001-01-01T00:00:00.001Z", "0001-01-01T00:00:00.000Z", "0001-01-01T00:00:00.001Z"),
        ("9999-12-31T23:59:59.998Z", "9999-12-31T23:59:59.999Z", "9999-12-31T23:59:59.998Z", "9999-12-31T23:59:59.999Z"),
        ("2024-02-29T01:02:03.4Z", "2024-02-29T01:02:03.45Z", "2024-02-29T01:02:03.400Z", "2024-02-29T01:02:03.450Z"),
        ("2026-01-02T23:59:00+23:59", "2026-01-03T00:00:00+23:59", "2026-01-02T00:00:00.000Z", "2026-01-02T00:01:00.000Z"),
        ("2026-01-01T00:00:00-23:59", "2026-01-01T00:01:00-23:59", "2026-01-01T23:59:00.000Z", "2026-01-02T00:00:00.000Z"),
    )
    for start, end, expected_start, expected_end in examples:
        store = call(factory)
        equal(method(store, "book", record(start=start, end=end)), normalized(start=expected_start, end=expected_end))


def baseline_intervals(factory):
    for start, end in (
        ("2026-01-02T10:00:00Z", "2026-01-02T10:00:00Z"),
        ("2026-01-02T11:00:00Z", "2026-01-02T10:00:00Z"),
        ("2026-01-02T10:00:00Z", "2026-01-02T12:00:00+02:00"),
        ("2026-01-02T10:00:00Z", "2026-01-02T11:00:00+02:00"),
    ):
        rejects(seeded(factory), "book", (record("b", "maple", start, end),), "INVALID_INPUT")


def baseline_inputs(factory):
    invalids = [None, [], "record", {}, {**record(), "extra": 1}]
    for field in ("id", "room", "start", "end"):
        item = record()
        del item[field]
        invalids.append(item)
    invalids += [{**record(), "id": value} for value in ("", None, 1, True, [])]
    invalids += [{**record(), "room": value} for value in (None, 1, True, [])]
    for item in invalids:
        rejects(call(factory), "book", (item,), "INVALID_INPUT")
    rejects(seeded(factory), "book", (record("b", "oak"),), "UNKNOWN_ROOM")
    rejects(seeded(factory), "book", (record("a", "maple"),), "DUPLICATE_ID")


def baseline_detached(factory):
    store = call(factory)
    original = record("z")
    returned = method(store, "book", original)
    require(isinstance(returned, dict), "book must return a dictionary")
    original["start"] = "changed input"
    returned["room"] = "changed result"
    equal(method(store, "list_bookings"), [normalized("z")])
    listed = method(store, "list_bookings")
    require(isinstance(listed, list), "list_bookings must return a list")
    listed[0]["id"] = "changed list item"
    listed.clear()
    equal(method(store, "list_bookings"), [normalized("z")])
    method(store, "book", record("a", "maple"))
    equal([item["id"] for item in method(store, "list_bookings")], ["a", "z"])
    whitespace_store = call(factory)
    equal(method(whitespace_store, "book", record(" ")), normalized(" "), "nonempty whitespace ID is permitted")


def reschedule_feature(factory):
    store = seeded(factory)
    result = method(store, "reschedule", "a", "2026-01-02T14:00:00+02:00", "2026-01-02T15:00:00+02:00")
    expected = normalized(start="2026-01-02T12:00:00.000Z", end="2026-01-02T13:00:00.000Z")
    equal(result, expected)
    equal(method(store, "list_bookings"), [expected])
    result["room"] = "maple"
    equal(method(store, "list_bookings"), [expected], "reschedule result aliases stored data")


def reschedule_self(factory):
    store = seeded(factory)
    equal(method(store, "reschedule", "a", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z"), normalized())
    method(store, "reschedule", "a", "2026-01-02T10:30:00Z", "2026-01-02T11:30:00Z")
    equal(method(store, "list_bookings"), [normalized(start="2026-01-02T10:30:00.000Z", end="2026-01-02T11:30:00.000Z")])


def reschedule_conflict(factory):
    store = seeded(factory)
    method(store, "book", record("b", start="2026-01-02T12:00:00Z", end="2026-01-02T13:00:00Z"))
    rejects(store, "reschedule", ("a", "2026-01-02T12:30:00Z", "2026-01-02T13:30:00Z"), "CONFLICT")
    method(store, "reschedule", "a", "2026-01-02T11:00:00Z", "2026-01-02T12:00:00Z")
    method(store, "book", record("c", "maple", "2026-01-02T13:00:00Z", "2026-01-02T14:00:00Z"))
    method(store, "reschedule", "a", "2026-01-02T13:00:00Z", "2026-01-02T14:00:00Z")


def reschedule_invalid(factory):
    for invalid in INVALID_TIMESTAMPS:
        for start, end in ((invalid, "2026-01-02T11:00:00Z"), ("2026-01-02T10:00:00Z", invalid)):
            rejects(seeded(factory), "reschedule", ("a", start, end), "INVALID_INPUT")
    for identifier, code in ((None, "INVALID_INPUT"), ("", "INVALID_INPUT"), (1, "INVALID_INPUT"), ("missing", "BOOKING_NOT_FOUND")):
        rejects(seeded(factory), "reschedule", (identifier, "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z"), code)
    rejects(seeded(factory), "reschedule", ("a", "2026-01-02T10:00:00Z", "2026-01-02T12:00:00+02:00"), "INVALID_INPUT")
    rejects(seeded(factory), "reschedule", ("a", "2026-01-02T11:00:00Z", "2026-01-02T10:00:00Z"), "INVALID_INPUT")


def availability_feature(factory):
    store = call(factory)
    equal(method(store, "available_rooms", "2026-01-02T10:00:00Z", "2026-01-02T11:00:00Z"), ["cedar", "maple"])
    method(store, "book", record())
    equal(method(store, "available_rooms", "2026-01-02T12:30:00+02:00", "2026-01-02T13:30:00+02:00"), ["maple"])
    method(store, "book", record("b", "maple"))
    equal(method(store, "available_rooms", "2026-01-02T10:15:00Z", "2026-01-02T10:45:00Z"), [])


def availability_boundaries(factory):
    store = seeded(factory)
    before = [dict(item) for item in method(store, "list_bookings")]
    for start, end in (("09:00:00", "10:00:00"), ("11:00:00", "12:00:00")):
        equal(method(store, "available_rooms", f"2026-01-02T{start}Z", f"2026-01-02T{end}Z"), ["cedar", "maple"])
    for start, end in (("09:00:00", "12:00:00"), ("10:00:00", "11:00:00"), ("09:30:00", "10:30:00")):
        equal(method(store, "available_rooms", f"2026-01-02T{start}Z", f"2026-01-02T{end}Z"), ["maple"])
    equal(method(store, "list_bookings"), before, "availability query changed bookings")


def availability_invalid(factory):
    for invalid in INVALID_TIMESTAMPS:
        for start, end in ((invalid, "2026-01-02T11:00:00Z"), ("2026-01-02T10:00:00Z", invalid)):
            rejects(seeded(factory), "available_rooms", (start, end), "INVALID_INPUT")
    rejects(seeded(factory), "available_rooms", ("2026-01-02T10:00:00Z", "2026-01-02T12:00:00+02:00"), "INVALID_INPUT")
    rejects(seeded(factory), "available_rooms", ("2026-01-02T11:00:00Z", "2026-01-02T10:00:00Z"), "INVALID_INPUT")


def batch_feature(factory):
    store = call(factory)
    inputs = [record("z", "maple"), record("a", start="2026-01-02T12:00:00+02:00", end="2026-01-02T13:00:00+02:00")]
    snapshot = [dict(item) for item in inputs]
    result = method(store, "book_many", inputs)
    equal(result, [normalized("z", "maple"), normalized("a")], "batch must return input order")
    equal(inputs, snapshot, "batch mutated input")
    inputs[0]["id"] = "changed"
    result[1]["room"] = "maple"
    equal(method(store, "list_bookings"), [normalized("a"), normalized("z", "maple")])
    equal(method(store, "book_many", []), [])
    equal(method(store, "list_bookings"), [normalized("a"), normalized("z", "maple")])


def batch_conflicts(factory):
    cases = (
        ([record("b", "maple"), record("c")], "CONFLICT"),
        ([record("b", "maple"), record("a", "maple", "2026-01-02T12:00:00Z", "2026-01-02T13:00:00Z")], "DUPLICATE_ID"),
        ([record("b", "maple"), record("c", "maple", "2026-01-02T12:30:00+02:00", "2026-01-02T13:30:00+02:00")], "CONFLICT"),
        ([record("b", "maple"), record("b", "maple", "2026-01-02T12:00:00Z", "2026-01-02T13:00:00Z")], "DUPLICATE_ID"),
    )
    for inputs, code in cases:
        rejects(seeded(factory), "book_many", (inputs,), code)


def batch_invalid(factory):
    for invalid in (None, {}, "records", (), [record("b", "maple"), None], [record("b", "maple"), {**record("c"), "extra": 1}]):
        rejects(seeded(factory), "book_many", (invalid,), "INVALID_INPUT")
    rejects(seeded(factory), "book_many", ([record("b", "maple"), record("c", "oak")],), "UNKNOWN_ROOM")
    for invalid in INVALID_TIMESTAMPS:
        for start, end in ((invalid, "2026-01-02T12:00:00Z"), ("2026-01-02T11:00:00Z", invalid)):
            rejects(seeded(factory), "book_many", ([record("b", "maple"), record("c", "maple", start, end)],), "INVALID_INPUT")
    rejects(seeded(factory), "book_many", ([record("b", "maple"), record("c", "maple", "2026-01-02T11:00:00Z", "2026-01-02T10:00:00Z")],), "INVALID_INPUT")
    rejects(seeded(factory), "book_many", ((item for item in []),), "INVALID_INPUT")


def batch_adjacency(factory):
    store = seeded(factory)
    method(store, "book_many", [record("b", start="2026-01-02T11:00:00Z", end="2026-01-02T12:00:00Z"), record("c", start="2026-01-02T12:00:00Z", end="2026-01-02T13:00:00Z"), record("d", "maple")])
    equal([item["id"] for item in method(store, "list_bookings")], ["a", "b", "c", "d"])


BASELINE_CHECKS = [
    ("baseline.interface", "baseline_rule", baseline_interface),
    ("baseline.overlap", "baseline_rule", baseline_overlap),
    ("baseline.adjacency_and_rooms", "baseline_rule", baseline_adjacency),
    ("baseline.offsets", "baseline_rule", baseline_offsets),
    ("baseline.timestamp_rejection", "baseline_rule", baseline_timestamp_rejection),
    ("baseline.valid_boundaries", "baseline_rule", baseline_valid_boundaries),
    ("baseline.interval_order", "baseline_rule", baseline_intervals),
    ("baseline.invalid_inputs", "baseline_rule", baseline_inputs),
    ("baseline.detached_and_sorted", "baseline_rule", baseline_detached),
]
TASK_CHECKS = {
    "baseline": [("baseline.feature", "feature", baseline_interface)],
    "reschedule": [("reschedule.feature", "feature", reschedule_feature), ("reschedule.self_exclusion", "new_rule", reschedule_self), ("reschedule.conflict_rollback", "new_rule", reschedule_conflict), ("reschedule.validation", "new_rule", reschedule_invalid)],
    "availability": [("availability.feature", "feature", availability_feature), ("availability.boundaries_read_only", "new_rule", availability_boundaries), ("availability.validation", "new_rule", availability_invalid)],
    "batch": [("batch.feature", "feature", batch_feature), ("batch.atomic_conflicts", "new_rule", batch_conflicts), ("batch.invalid_atomicity", "new_rule", batch_invalid), ("batch.adjacency", "new_rule", batch_adjacency)],
}


def aggregate(statuses: list[str]) -> str:
    if "fail" in statuses:
        return "fail"
    if statuses and all(status == "pass" for status in statuses):
        return "pass"
    return "unevaluable"


def empty_report(task: str) -> dict:
    return {"schema_version": 1, "task": task, "status": "completed", "build": "unevaluable", "baseline_rules": "unevaluable", "new_rules": "unevaluable", "feature": "unevaluable", "rules": "unevaluable", "checks": [], "errors": []}


def evaluate_factory(factory, task: str) -> dict:
    """Run checks against a trusted callable factory; useful for calibration."""
    if task not in TASKS:
        raise ValueError(f"unknown task: {task}")
    result = empty_report(task)
    result["build"] = "pass"
    missing = task != "baseline" and not callable(getattr(factory, METHODS[task], None))
    for check_id, group, function in BASELINE_CHECKS + TASK_CHECKS[task]:
        check = {"id": check_id, "group": group, "status": "pass"}
        if missing and group in ("new_rule", "feature"):
            check.update(status="fail" if group == "feature" else "unevaluable", detail=f"missing requested method {METHODS[task]}")
        else:
            try:
                function(factory)
            except ContractFailure as error:
                check.update(status="fail", detail=str(error)[:700])
            except BaseException as error:
                check.update(status="unevaluable", detail=detail(error))
                result["status"] = "evaluator_error"
                result["errors"].append({"kind": "evaluator_error", "stage": check_id, "message": detail(error)})
        result["checks"].append(check)
    for field, group in (("baseline_rules", "baseline_rule"), ("new_rules", "new_rule"), ("feature", "feature")):
        result[field] = aggregate([check["status"] for check in result["checks"] if check["group"] == group])
    result["rules"] = aggregate([result["baseline_rules"]] + ([] if task == "baseline" else [result["new_rules"]]))
    # Completing the feature requires preserving all evaluated contract behavior.
    result["feature"] = aggregate([result["feature"], result["rules"]])
    return result


def evaluate_submission(submission_dir: str | Path, task: str) -> dict:
    """Import one trusted calibration submission and evaluate its observable API.

    For untrusted submissions call the CLI in an external sandbox instead.
    """
    if task not in TASKS:
        raise ValueError(f"unknown task: {task}")
    output = CappedOutput()
    result = empty_report(task)
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        source = Path(submission_dir) / "booking.py"
        try:
            specification = importlib.util.spec_from_file_location("canary_submission_booking", source)
            if specification is None or specification.loader is None:
                raise ImportError("cannot load booking.py")
            module = importlib.util.module_from_spec(specification)
            sys.modules[specification.name] = module
            # Compile source directly, avoiding stale bytecode caches and scripts.
            exec(compile(source.read_bytes(), str(source), "exec"), module.__dict__)
            factory = getattr(module, "BookingStore")
            if not isinstance(factory, type):
                raise TypeError("BookingStore must be a class")
        except BaseException as error:
            result.update(status="build_failure", build="fail", feature="fail")
            result["errors"].append({"kind": "submission_import", "stage": "import", "message": detail(error)})
        else:
            result = evaluate_factory(factory, task)
        finally:
            sys.modules.pop("canary_submission_booking", None)
    result["submission_output"] = output.text
    result["submission_output_truncated"] = output.truncated
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("submission_dir")
    parser.add_argument("task", choices=TASKS)
    args = parser.parse_args(argv)
    try:
        result = evaluate_submission(args.submission_dir, args.task)
    except BaseException as error:
        result = empty_report(args.task)
        result["status"] = "evaluator_error"
        result["errors"].append({"kind": "evaluator_error", "stage": "controller", "message": detail(error)})
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"] == "evaluator_error" else 0


if __name__ == "__main__":
    raise SystemExit(main())

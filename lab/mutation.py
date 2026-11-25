"""Planted-bug (mutation) scoring for the hidden evaluator.

Each mutant applies one targeted source change to a trusted reference solution
at a contract risk point, then runs the evaluator in-process. A mutant is
"killed" when any check fails. The report separates kills by the fixed,
hand-written checks from kills by the randomized differential checks, so the
added strength of the randomized checks is visible.

Mutants are our own code derived from trusted references, so they run
in-process; agent submissions are never evaluated this way.

    python3 -m lab.mutation --output artifacts/mutation-01
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import types

from evaluator.evaluate import evaluate_factory


ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
    "baseline": ROOT / "fixtures/baseline/booking.py",
    "reschedule": ROOT / "fixtures/reference/reschedule/booking.py",
    "availability": ROOT / "fixtures/reference/availability/booking.py",
    "batch": ROOT / "fixtures/reference/batch/booking.py",
}

# (id, task, risk point, old text, new text). Each old text must occur exactly once.
# Equivalent mutants behave identically to the reference and are excluded from the kill rate.
EQUIVALENT = {
    "offset-hour-24": "Python's timezone() rejects offsets of 24 hours or more, so +24:00 still raises INVALID_INPUT.",
}
MUTANTS = [
    ("touching-start", "baseline", "half-open overlap: start", 'and record["start"] < other["end"]', 'and record["start"] <= other["end"]'),
    ("touching-end", "baseline", "half-open overlap: end", 'and other["start"] < record["end"]', 'and other["start"] <= record["end"]'),
    ("ignore-room", "baseline", "same-room condition", 'and other["room"] == record["room"]', "and True"),
    ("offset-sign", "baseline", "offset sign", 'if match.group(9) == "-":', 'if match.group(9) == "+":'),
    ("offset-hour-24", "baseline", "offset hour range", "offset_hour > 23", "offset_hour > 24"),

    ("offset-minute-60", "baseline", "offset minute range", "offset_minute > 59", "offset_minute > 60"),
    ("fraction-pad", "baseline", "fraction normalization", '.ljust(6, "0")', '.rjust(6, "0")'),
    ("fraction-4-digits", "baseline", "fraction digits", "{1,3}", "{1,4}"),
    ("empty-interval", "baseline", "end strictly after start", "if end_instant <= start_instant:", "if end_instant < start_instant:"),
    ("ignore-offset", "baseline", "UTC conversion", "return local.astimezone(timezone.utc)", "return local.replace(tzinfo=timezone.utc)"),
    ("unsorted-list", "baseline", "list order", "for key in sorted(self._bookings)]", "for key in self._bookings]"),
    ("aliased-book-result", "baseline", "detached results", "return dict(normalized)", "return normalized"),
    ("aliased-list", "baseline", "detached listing", "return [dict(self._bookings[key])", "return [self._bookings[key]"),
    ("no-duplicate-check", "baseline", "duplicate IDs", 'if normalized["id"] in self._bookings:', "if False:"),
    ("empty-id-allowed", "baseline", "ID validation", 'if not isinstance(record["id"], str) or not record["id"]:', 'if not isinstance(record["id"], str):'),
    ("extra-fields-allowed", "baseline", "record shape", "set(record) != _FIELDS", "not _FIELDS <= set(record)"),
    ("store-before-conflict", "baseline", "rejected book leaves store unchanged",
     '        if self._has_conflict(normalized):\n            raise ValueError("CONFLICT")\n        self._bookings[normalized["id"]] = normalized\n',
     '        self._bookings[normalized["id"]] = normalized\n        if self._has_conflict(normalized, exclude_id=normalized["id"]):\n            raise ValueError("CONFLICT")\n'),
    ("no-self-exclusion", "reschedule", "exclude the booking being changed", "exclude_id=booking_id)", "exclude_id=None)"),
    ("reschedule-before-conflict", "reschedule", "rejected reschedule leaves store unchanged",
     '        if self._has_conflict(changed, exclude_id=booking_id):\n            raise ValueError("CONFLICT")\n        self._bookings[booking_id] = changed\n',
     '        self._bookings[booking_id] = changed\n        if self._has_conflict(changed, exclude_id=booking_id):\n            raise ValueError("CONFLICT")\n'),
    ("not-found-code", "reschedule", "unknown ID error code", 'raise ValueError("BOOKING_NOT_FOUND")', 'raise ValueError("INVALID_INPUT")'),
    ("aliased-reschedule-result", "reschedule", "detached result", "return dict(changed)", "return changed"),
    ("reschedule-changes-room", "reschedule", "room preserved", '"room": current["room"],', '"room": "cedar",'),
    ("reschedule-empty-id", "reschedule", "empty ID is INVALID_INPUT", "if not isinstance(booking_id, str) or not booking_id:", "if not isinstance(booking_id, str):"),
    ("rooms-unsorted", "availability", "sorted room list", "return [room for room in _ROOMS", "return [room for room in reversed(_ROOMS)"),
    ("availability-ignores-room", "availability", "per-room availability", 'if not self._has_conflict({"room": room,', 'if not self._has_conflict({"room": "cedar",'),
    ("availability-no-validation", "availability", "query validation", "normalized_start, normalized_end = _normalize_interval(start, end)", "normalized_start, normalized_end = start, end"),
    ("availability-inverted", "availability", "free vs booked", 'if not self._has_conflict({"room": room,', 'if self._has_conflict({"room": room,'),
    ("non-atomic-batch", "batch", "atomic batch",
     "        staged = BookingStore()\n        staged._bookings = {key: dict(value) for key, value in self._bookings.items()}\n        results = [staged.book(record) for record in records]\n        self._bookings = staged._bookings\n",
     "        results = [self.book(record) for record in records]\n"),
    ("batch-accepts-tuple", "batch", "list-only input", "if not isinstance(records, list):", "if not isinstance(records, (list, tuple)):"),
    ("no-intra-batch-check", "batch", "conflicts within the batch",
     "        results = [staged.book(record) for record in records]\n",
     "        results = []\n        for record in records:\n            probe = BookingStore()\n            probe._bookings = dict(self._bookings)\n            results.append(probe.book(record))\n        for item in results:\n            staged._bookings[item['id']] = dict(item)\n"),
    ("batch-mutates-input", "batch", "input not mutated", "        return results\n", "        records[:] = []\n        return results\n"),
    ("batch-wrong-order", "batch", "results in input order", "        return results\n", "        return sorted(results, key=lambda item: item['id'])\n"),
]


def apply(task, old, new):
    source = SOURCES[task].read_text(encoding="utf-8")
    if source.count(old) != 1:
        raise ValueError(f"mutation text must occur exactly once in {task} reference: {old!r}")
    return source.replace(old, new)


def load(source, name):
    module = types.ModuleType(f"mutant_{name.replace('-', '_')}")
    exec(compile(source, f"<mutant {name}>", "exec"), module.__dict__)
    return module.BookingStore


def score(mutant):
    identifier, task, risk, old, new = mutant
    result = evaluate_factory(load(apply(task, old, new), identifier), task)
    failed = [check["id"] for check in result["checks"] if check["status"] == "fail"]
    unevaluable = [check["id"] for check in result["checks"] if check["status"] == "unevaluable"]
    fixed = [check for check in failed if not check.endswith(".randomized_differential")]
    randomized = [check for check in failed if check.endswith(".randomized_differential")]
    details = {check["id"]: check.get("detail", "") for check in result["checks"] if check["status"] != "pass"}
    return {"id": identifier, "task": task, "risk_point": risk,
            "equivalent": EQUIVALENT.get(identifier),
            "killed": bool(failed), "killed_by_fixed_checks": bool(fixed),
            "killed_by_randomized_checks": bool(randomized),
            "failed_checks": failed, "unevaluable_checks": unevaluable,
            "evaluator_status": result["status"], "details": details}


def run(output=None):
    started = time.monotonic()
    references = {task: evaluate_factory(load(path.read_text(encoding="utf-8"), f"reference-{task}"), task)
                  for task, path in SOURCES.items()}
    reference_failures = {task: [c["id"] for c in r["checks"] if c["status"] != "pass"]
                          for task, r in references.items() if r["feature"] != "pass"}
    outcomes = [score(mutant) for mutant in MUTANTS]
    scored = [o for o in outcomes if not o["equivalent"]]
    summary = {
        "schema_version": 1,
        "mutants": len(outcomes),
        "equivalent": [o["id"] for o in outcomes if o["equivalent"]],
        "scored": len(scored),
        "killed": sum(o["killed"] for o in scored),
        "killed_by_fixed_checks": sum(o["killed_by_fixed_checks"] for o in scored),
        "killed_by_randomized_checks": sum(o["killed_by_randomized_checks"] for o in scored),
        "killed_only_by_randomized_checks": [o["id"] for o in scored if o["killed_by_randomized_checks"] and not o["killed_by_fixed_checks"]],
        "survivors": [o["id"] for o in scored if not o["killed"]],
        "equivalent_but_killed": [o["id"] for o in outcomes if o["equivalent"] and o["killed"]],
        "evaluator_errors": [o["id"] for o in outcomes if o["evaluator_status"] == "evaluator_error"],
        "references_pass": not reference_failures,
        "reference_failures": reference_failures,
        "duration_seconds": round(time.monotonic() - started, 2),
        "outcomes": outcomes,
    }
    if output is not None:
        output = Path(output)
        if output.exists():
            raise FileExistsError("Mutation output exists; choose a new directory")
        output.mkdir(parents=True)
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    summary = run(args.output)
    print(json.dumps({key: summary[key] for key in summary if key != "outcomes"}, indent=2))


if __name__ == "__main__":
    main()

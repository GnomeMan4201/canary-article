"""Calibrate the isolated evaluator with known fixtures, never agent trials."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from lab.runner import ROOT, evaluate, fingerprint, write_json


def cases() -> list[dict]:
    baseline = (ROOT / "fixtures/baseline/booking.py").read_text()
    definitions = []

    def add(name, task, source, fields, *, check=None, timeout=20, raw=None, diagnostic=None):
        definitions.append({"id": name, "task": task, "source": source,
                            "expected_fields": fields, "expected_check": check,
                            "timeout_seconds": timeout, "expected_raw": raw or {},
                            "expected_diagnostic": diagnostic})

    passing = {"status": "completed", "build": "pass", "baseline_rules": "pass",
               "rules": "pass", "feature": "pass"}
    add("correct-baseline", "baseline", baseline, passing)
    for task in ("reschedule", "availability", "batch"):
        source = (ROOT / "fixtures/reference" / task / "booking.py").read_text()
        add(f"correct-{task}", task, source, {**passing, "new_rules": "pass"})

    failure = {"status": "completed", "build": "pass", "rules": "fail", "feature": "fail"}
    add("allows-overlap", "baseline", baseline + '''

class BookingStore(BookingStore):
    def _has_conflict(self, record, exclude_id=None):
        return False
''', failure, check={"id": "baseline.overlap", "status": "fail"})

    offset_expression = "local.astimezone(timezone.utc)"
    if baseline.count(offset_expression) != 1:
        raise ValueError("Offset calibration mutation no longer matches the baseline")
    add("ignores-offset", "baseline",
        baseline.replace(offset_expression, "local.replace(tzinfo=timezone.utc)"),
        failure, check={"id": "baseline.offsets", "status": "fail"})

    add("mutates-before-rejection", "baseline", baseline + '''

class BookingStore(BookingStore):
    def book(self, record):
        try:
            return super().book(record)
        except ValueError:
            self._bookings.clear()
            raise
''', failure, check={"id": "baseline.overlap", "status": "fail",
                    "detail_contains": "changed stored state"})

    add("non-atomic-batch", "batch", baseline + '''

class BookingStore(BookingStore):
    def book_many(self, records):
        if not isinstance(records, list):
            raise ValueError("INVALID_INPUT")
        return [self.book(record) for record in records]
''', failure, check={"id": "batch.atomic_conflicts", "status": "fail",
                    "detail_contains": "changed stored state"})

    for task in ("reschedule", "availability", "batch"):
        add(f"missing-{task}", task, baseline,
            {"status": "completed", "build": "pass", "baseline_rules": "pass",
             "new_rules": "unevaluable", "rules": "unevaluable", "feature": "fail"})

    build_failure = {"status": "build_failure", "build": "fail",
                     "baseline_rules": "unevaluable", "new_rules": "unevaluable",
                     "rules": "unevaluable", "feature": "fail"}
    add("syntax-failure", "baseline", "def broken(\n", build_failure)
    add("import-failure", "baseline", "raise RuntimeError('calibration import failure')\n", build_failure)
    add("missing-export", "baseline", "value = 1\n", build_failure)
    add("noisy-import", "baseline", "print('calibration noise ' * 10000)\n" + baseline,
        {**passing, "submission_output_truncated": True})
    add("import-timeout", "baseline", "while True:\n    pass\n",
        {"status": "evaluator_error", "build": "unevaluable", "baseline_rules": "unevaluable",
         "new_rules": "unevaluable", "rules": "unevaluable", "feature": "unevaluable"},
        timeout=2, raw={"timeout": True}, diagnostic="timeout")
    return definitions


def mismatches(case: dict, report: dict, raw: dict) -> list[str]:
    problems = []
    for field, expected in case["expected_fields"].items():
        if report.get(field) != expected:
            problems.append(f"report.{field}: expected {expected!r}, got {report.get(field)!r}")
    for field, expected in case.get("expected_raw", {}).items():
        if raw.get(field) != expected:
            problems.append(f"process.{field}: expected {expected!r}, got {raw.get(field)!r}")
    expected_check = case.get("expected_check")
    if expected_check:
        found = next((item for item in report.get("checks", []) if item.get("id") == expected_check["id"]), None)
        if found is None:
            problems.append(f"missing check {expected_check['id']}")
        else:
            if found.get("status") != expected_check["status"]:
                problems.append(f"{expected_check['id']}: expected {expected_check['status']}, got {found.get('status')}")
            if expected_check.get("detail_contains", "") not in found.get("detail", ""):
                problems.append(f"{expected_check['id']}: missing expected diagnostic text")
    if case.get("expected_diagnostic") and not any(
            item.get("kind") == case["expected_diagnostic"] for item in report.get("errors", [])):
        problems.append(f"missing {case['expected_diagnostic']} diagnostic")
    if case["id"] == "noisy-import":
        if len(report.get("submission_output", "")) > 2048:
            problems.append("captured submission output exceeds 2048 characters")
        try:
            parsed = json.loads(raw.get("stdout", ""))
        except (ValueError, TypeError):
            problems.append("noisy import did not produce a single JSON document")
        else:
            if parsed != report:
                problems.append("raw JSON and parsed report disagree")
    return problems


def run_calibration(output: Path, image: str) -> dict:
    """Run every case in Docker and preserve inputs plus raw process evidence."""
    output = output.resolve()
    if output.exists():
        raise FileExistsError("Calibration destination exists; preserve it and choose a new directory")
    definitions = cases()
    versions = fingerprint()
    output.mkdir(parents=True)
    summary = {"schema_version": 1, "phase": "calibration", "status": "fail",
               "image": image, "source_hashes": versions, "cases": []}
    # An interrupted calibration must never resemble completed passing evidence.
    write_json(output / "summary.json", summary)
    for case in definitions:
        folder = output / "cases" / case["id"]
        folder.mkdir(parents=True)
        (folder / "booking.py").write_text(case["source"])
        expectation = {key: value for key, value in case.items() if key != "source"}
        write_json(folder / "expectation.json", expectation)
        try:
            with tempfile.TemporaryDirectory(prefix="canary-calibration-") as temporary:
                snapshot = Path(temporary)
                (snapshot / "booking.py").write_text(case["source"])
                report, raw = evaluate(snapshot, case["task"], image, timeout=case["timeout_seconds"])
            problems = mismatches(case, report, raw)
        except Exception as error:
            message = f"{type(error).__name__}: {str(error)[:1000]}"
            report = {"status": "evaluator_error", "errors": [{"kind": "calibration_process", "message": message}]}
            raw = {"stdout": "", "stderr": "", "exit_code": None, "timeout": False,
                   "calibration_exception": message}
            problems = [message]
        write_json(folder / "result.json", report)
        write_json(folder / "process.json", raw)
        outcome = {"id": case["id"], "task": case["task"], "phase": "calibration",
                   "status": "pass" if not problems else "fail", "problems": problems,
                   "observed_status": report.get("status"),
                   "evidence": str(folder.relative_to(output))}
        summary["cases"].append(outcome)
        write_json(output / "summary.json", summary)
    summary["source_stable"] = fingerprint() == versions
    summary["status"] = "pass" if summary["source_stable"] and all(
        case["status"] == "pass" for case in summary["cases"]) else "fail"
    if not summary["source_stable"]:
        summary["error"] = "Source files changed during calibration; repeat in a new evidence directory"
    write_json(output / "summary.json", summary)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", default="canary-lab-runtime:local")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/calibration")
    arguments = parser.parse_args(argv)
    try:
        summary = run_calibration(arguments.output, arguments.image)
    except Exception as error:
        print(json.dumps({"phase": "calibration", "status": "fail", "error": f"{type(error).__name__}: {error}"}))
        return 1
    print(json.dumps({"phase": "calibration", "status": summary["status"],
                      "cases": len(summary["cases"]), "output": str(arguments.output)}))
    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())

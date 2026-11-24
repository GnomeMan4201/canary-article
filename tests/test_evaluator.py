"""Calibration of independent checks; these are not agent experiment runs."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evaluator import evaluate


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "fixtures" / "baseline"


def factory_at(directory):
    spec = importlib.util.spec_from_file_location("trusted_calibration", directory / "booking.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.BookingStore


class EvaluatorCalibration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = factory_at(BASELINE)

    def checked(self, report, check_id):
        return next(item for item in report["checks"] if item["id"] == check_id)

    def test_correct_baseline_and_all_references_pass(self):
        for task in evaluate.TASKS:
            with self.subTest(task=task):
                directory = BASELINE if task == "baseline" else ROOT / "fixtures" / "reference" / task
                report = evaluate.evaluate_submission(directory, task)
                self.assertEqual(report["status"], "completed", report["errors"])
                self.assertEqual(report["build"], "pass")
                self.assertEqual(report["rules"], "pass", report["checks"])
                self.assertEqual(report["feature"], "pass")
                self.assertTrue(all(check["status"] == "pass" for check in report["checks"]))

    def test_missing_method_is_not_compliant(self):
        for task in ("reschedule", "availability", "batch"):
            with self.subTest(task=task):
                report = evaluate.evaluate_factory(self.baseline, task)
                self.assertEqual(report["baseline_rules"], "pass")
                self.assertEqual(report["feature"], "fail")
                self.assertEqual(report["new_rules"], "unevaluable")
                self.assertEqual(report["rules"], "unevaluable")

    def test_overlap_mutation_is_detected(self):
        class OverlapAllowed(self.baseline):
            def _has_conflict(self, record, exclude_id=None):
                return False

        report = evaluate.evaluate_factory(OverlapAllowed, "baseline")
        self.assertEqual(self.checked(report, "baseline.overlap")["status"], "fail")
        self.assertEqual(report["rules"], "fail")
        self.assertEqual(report["status"], "completed")

    def test_offset_mutation_is_detected(self):
        text = (BASELINE / "booking.py").read_text()
        original = "local.astimezone(timezone.utc)"
        self.assertIn(original, text)
        text = text.replace(original, "local.replace(tzinfo=timezone.utc)")
        with tempfile.TemporaryDirectory() as temporary:
            (Path(temporary) / "booking.py").write_text(text)
            report = evaluate.evaluate_submission(temporary, "baseline")
        self.assertEqual(self.checked(report, "baseline.offsets")["status"], "fail")

    def test_mutation_before_rejection_is_detected(self):
        class StateLoss(self.baseline):
            def book(self, record):
                try:
                    return super().book(record)
                except ValueError:
                    self._bookings.clear()
                    raise

        report = evaluate.evaluate_factory(StateLoss, "baseline")
        check = self.checked(report, "baseline.overlap")
        self.assertEqual(check["status"], "fail")
        self.assertIn("changed stored state", check["detail"])

    def test_live_reference_return_is_detected(self):
        class Aliased(self.baseline):
            def list_bookings(self):
                return [self._bookings[key] for key in sorted(self._bookings)]

        report = evaluate.evaluate_factory(Aliased, "baseline")
        self.assertEqual(self.checked(report, "baseline.detached_and_sorted")["status"], "fail")

    def test_non_atomic_batch_is_detected(self):
        class PartialBatch(self.baseline):
            def book_many(self, records):
                if not isinstance(records, list):
                    raise ValueError("INVALID_INPUT")
                return [self.book(record) for record in records]

        report = evaluate.evaluate_factory(PartialBatch, "batch")
        check = self.checked(report, "batch.atomic_conflicts")
        self.assertEqual(check["status"], "fail")
        self.assertIn("changed stored state", check["detail"])

    def test_wrong_return_type_is_submission_failure(self):
        class WrongShape(self.baseline):
            def list_bookings(self):
                return None

        report = evaluate.evaluate_factory(WrongShape, "baseline")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["rules"], "fail")
        self.assertEqual(report["errors"], [])

    def test_submission_exception_is_observed_failure(self):
        class Raises(self.baseline):
            def book(self, record):
                raise RuntimeError("implementation defect")

        report = evaluate.evaluate_factory(Raises, "baseline")
        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["rules"], "fail")
        self.assertEqual(report["errors"], [])

    def test_evaluator_fault_is_not_submission_failure(self):
        def evaluator_fault(factory):
            raise RuntimeError("broken evaluator")

        with patch.object(evaluate, "BASELINE_CHECKS", [("calibration.evaluator_fault", "baseline_rule", evaluator_fault)]):
            report = evaluate.evaluate_factory(self.baseline, "baseline")
        self.assertEqual(report["status"], "evaluator_error")
        self.assertEqual(report["rules"], "unevaluable")
        self.assertEqual(report["errors"][0]["kind"], "evaluator_error")

    def test_build_failures_keep_behavior_unevaluable(self):
        for source in ("not valid Python !!!", "x = 1", "raise RuntimeError('import failure')"):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as temporary:
                (Path(temporary) / "booking.py").write_text(source)
                report = evaluate.evaluate_submission(temporary, "reschedule")
                self.assertEqual(report["status"], "build_failure")
                self.assertEqual(report["build"], "fail")
                self.assertEqual(report["feature"], "fail")
                self.assertEqual(report["rules"], "unevaluable")

    def test_missing_file_is_build_failure(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = evaluate.evaluate_submission(temporary, "baseline")
        self.assertEqual(report["status"], "build_failure")

    def test_cli_is_single_json_and_bounds_import_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = "print('x' * 100000)\n" + (BASELINE / "booking.py").read_text()
            (Path(temporary) / "booking.py").write_text(source)
            process = subprocess.run([sys.executable, "-m", "evaluator.evaluate", temporary, "baseline"], cwd=ROOT, text=True, capture_output=True, timeout=10)
        self.assertEqual(process.returncode, 0, process.stderr)
        report = json.loads(process.stdout)
        self.assertEqual(len(process.stdout.splitlines()), 1)
        self.assertLessEqual(len(report["submission_output"]), 2048)
        self.assertTrue(report["submission_output_truncated"])
        self.assertEqual(report["rules"], "pass")

    def test_aggregate_never_calls_missing_checks_a_pass(self):
        self.assertEqual(evaluate.aggregate([]), "unevaluable")
        self.assertEqual(evaluate.aggregate(["pass", "unevaluable"]), "unevaluable")
        self.assertEqual(evaluate.aggregate(["fail", "unevaluable"]), "fail")


if __name__ == "__main__":
    unittest.main()

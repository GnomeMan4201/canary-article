"""Controller tests use fake evaluator results and never launch Docker."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab import calibrate


class CalibrationControllerTests(unittest.TestCase):
    def test_cases_include_named_mutations_and_timeout(self):
        definitions = calibrate.cases()
        self.assertEqual(len(definitions), 16)
        self.assertEqual(len({case["id"] for case in definitions}), 16)
        timeout = next(case for case in definitions if case["id"] == "import-timeout")
        self.assertEqual(timeout["timeout_seconds"], 2)
        self.assertEqual(timeout["expected_diagnostic"], "timeout")

    def test_wrong_named_check_fails_expectation(self):
        case = next(item for item in calibrate.cases() if item["id"] == "allows-overlap")
        report = {**case["expected_fields"], "checks": [{"id": "baseline.overlap", "status": "pass"}]}
        self.assertTrue(calibrate.mismatches(case, report, {}))

    def test_fake_suite_saves_inputs_and_failed_case(self):
        definitions = [
            {"id": "one", "task": "baseline", "source": "x = 1\n", "expected_fields": {"status": "completed"}, "timeout_seconds": 20},
            {"id": "two", "task": "batch", "source": "x = 2\n", "expected_fields": {"status": "build_failure"}, "timeout_seconds": 20},
        ]
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "calibration"
            with patch.object(calibrate, "cases", return_value=definitions), patch.object(calibrate, "fingerprint", return_value={"source": "hash"}), patch.object(calibrate, "evaluate", return_value=({"status": "completed"}, {"stdout": "{}"})) as evaluator:
                summary = calibrate.run_calibration(output, "fake-image")
            self.assertEqual(evaluator.call_count, 2)
            self.assertEqual(summary["status"], "fail")
            self.assertEqual([case["status"] for case in summary["cases"]], ["pass", "fail"])
            self.assertEqual((output / "cases/one/booking.py").read_text(), "x = 1\n")
            self.assertEqual(json.loads((output / "summary.json").read_text()), summary)

    def test_source_change_prevents_passing_evidence(self):
        definition = {"id": "one", "task": "baseline", "source": "x = 1\n", "expected_fields": {"status": "completed"}, "timeout_seconds": 20}
        with tempfile.TemporaryDirectory() as temporary, patch.object(calibrate, "cases", return_value=[definition]), patch.object(calibrate, "fingerprint", side_effect=[{"source": "before"}, {"source": "after"}]), patch.object(calibrate, "evaluate", return_value=({"status": "completed"}, {})):
            summary = calibrate.run_calibration(Path(temporary) / "calibration", "fake-image")
        self.assertEqual(summary["status"], "fail")
        self.assertFalse(summary["source_stable"])

    def test_existing_evidence_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(FileExistsError):
                calibrate.run_calibration(Path(temporary), "fake-image")


if __name__ == "__main__":
    unittest.main()

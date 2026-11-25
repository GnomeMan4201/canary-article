"""Re-scoring is a labeled re-analysis: hash-checked, side by side, never touching the source cohort."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from lab import rescore, runner


def evaluation(rules="pass", failed=()):
    checks = [{"id": "baseline.overlap", "group": "baseline_rule", "status": "pass"}]
    checks += [{"id": check, "group": "new_rule", "status": "fail"} for check in failed]
    return {"schema_version": 1, "task": "reschedule", "status": "completed", "build": "pass",
            "baseline_rules": "pass", "new_rules": rules, "rules": rules, "feature": rules,
            "checks": checks, "errors": []}


class RescoreTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.cohort = self.base / "cohort"
        self.plan = {"phase": "main", "runs": [], "runtime": {"image_id": "sha256:old"}}

    def add(self, run_id, marker="exact", tamper=False):
        self.plan["runs"].append({"run_id": run_id, "task": "reschedule", "condition": "B"})
        snapshot = self.cohort / "runs" / run_id / "snapshot"
        snapshot.mkdir(parents=True)
        (snapshot / "booking.py").write_text("# submission\n")
        hashes = {"booking.py": runner.sha(snapshot / "booking.py")}
        if tamper:
            (snapshot / "booking.py").write_text("# changed after recording\n")
        runner.write_json(snapshot.parent / "result.json", {"marker": {"status": marker},
                          "evaluation": evaluation(), "snapshot_hashes": hashes})

    def run_rescore(self, new_evaluation):
        runner.write_json(self.cohort / "plan.json", self.plan)
        before = {p: p.read_bytes() for p in self.cohort.rglob("*") if p.is_file()}
        with patch.object(runner, "evaluate", return_value=(new_evaluation, {"exit_code": 0})) as evaluate:
            summary = rescore.rescore(self.cohort, self.base / "out", "sha256:new")
        self.assertEqual({p: p.read_bytes() for p in self.cohort.rglob("*") if p.is_file()}, before)
        return summary, evaluate

    def test_unchanged_outcomes_are_reported_side_by_side(self):
        self.add("r1")
        summary, _ = self.run_rescore(evaluation())
        self.assertEqual((summary["rescored"], summary["changed_outcomes"]), (1, []))
        self.assertEqual(summary["original_image_id"], "sha256:old")
        self.assertTrue((self.base / "out/runs/r1/evaluation.json").is_file())

    def test_new_failures_with_exact_marker_are_surfaced(self):
        self.add("r1")
        summary, _ = self.run_rescore(evaluation("fail", ["reschedule.randomized_differential"]))
        self.assertEqual(summary["changed_outcomes"], ["r1"])
        self.assertEqual(summary["exact_marker_and_now_failing"], ["r1"])
        self.assertEqual(summary["runs"][0]["newly_failed_checks"], ["reschedule.randomized_differential"])

    def test_tampered_snapshot_is_not_evaluated(self):
        self.add("r1", tamper=True)
        summary, evaluate = self.run_rescore(evaluation())
        evaluate.assert_not_called()
        self.assertEqual(summary["not_rescored"], {"r1": "snapshot_mismatch"})

    def test_existing_output_is_never_overwritten(self):
        self.add("r1")
        (self.base / "out").mkdir()
        runner.write_json(self.cohort / "plan.json", self.plan)
        with self.assertRaises(FileExistsError):
            rescore.rescore(self.cohort, self.base / "out", "sha256:new")


if __name__ == "__main__":
    unittest.main()

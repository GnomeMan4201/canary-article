"""Report accounting must preserve incomplete and contradictory evidence."""

import json
from pathlib import Path
import tempfile
import unittest

from lab.report import build_report


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cohort = self.root / "cohort"
        self.cohort.mkdir()
        self.output = self.root / "report"
        self.plan = {"phase": "pilot", "runs": []}

    def add_run(self, run_id, marker="exact", rules="pass", condition="B", task="batch", recording="recorded", **overrides):
        planned = {"run_id": run_id, "task": task, "condition": condition}
        self.plan["runs"].append(planned)
        folder = self.cohort / "runs" / run_id
        folder.mkdir(parents=True)
        if recording == "interrupted":
            (folder / "attempt.json").write_text("{}")
        if recording != "recorded":
            return
        result = {
            **planned, "phase": "pilot", "termination": "completed",
            "marker": {"status": marker},
            "evaluation": {"schema_version": 1, "build": "pass", "baseline_rules": rules,
                           "new_rules": rules, "feature": rules, "rules": rules,
                           "status": "completed", "checks": [], "errors": []},
            "duration_seconds": 1.2, "usage": None,
        }
        result.update(overrides)
        (folder / "result.json").write_text(json.dumps(result))

    def build(self):
        (self.cohort / "plan.json").write_text(json.dumps(self.plan))
        return build_report(self.cohort, self.output)

    def test_four_cells_exclusions_and_breakdown(self):
        self.add_run("ep")
        self.add_run("ef", rules="fail")
        self.add_run("np", marker="absent", task="availability")
        self.add_run("nf", marker="malformed", rules="fail")
        self.add_run("unobserved", marker="unobserved", rules="fail")
        self.add_run("unevaluable", rules="unevaluable")
        self.add_run("control", marker="not_applicable", condition="A")
        self.add_run("missing", recording="not_attempted")
        self.add_run("interrupted", recording="interrupted")
        report = self.build()
        summary = report["summary"]
        self.assertEqual(summary["planned"], 9)
        self.assertEqual(summary["recording"], {"recorded": 7, "not_attempted": 1, "interrupted": 1})
        self.assertEqual(summary["four_cells"], {"exact_pass": 1, "exact_fail": 1, "noncompliant_pass": 1, "noncompliant_fail": 1})
        self.assertEqual(summary["four_cell_excluded"], {"unobserved_marker": 1, "unevaluable_rules": 1, "no_marker_condition": 1, "not_attempted": 1, "interrupted": 1})
        self.assertEqual(summary["exact_marker_unevaluable_rules"], 1)
        self.assertEqual(summary["rates"]["failure_given_exact"]["value"], .5)
        self.assertEqual(summary["rates"]["noncompliance_among_observed_markers"]["denominator"], 5)
        self.assertEqual(report["by_task"]["availability"]["four_cells"]["noncompliant_pass"], 1)
        self.assertEqual(report["by_condition"]["A"]["four_cell_included"], 0)
        self.assertEqual(json.loads((self.output / "report.json").read_text()), report)

    def test_empty_denominators_are_null(self):
        report = self.build()
        for rate in report["summary"]["rates"].values():
            self.assertIsNone(rate["value"])
            self.assertEqual(rate["denominator"], 0)
        self.assertIn("Undefined", (self.output / "report.html").read_text())

    def test_untrusted_evidence_and_task_are_escaped(self):
        payload = '</pre><script>alert("oops")</script>'
        self.add_run("unsafe", task=payload, evaluation={"rules": "pass", "checks": [{"name": payload, "actual": payload}], "errors": [payload]})
        self.build()
        html = (self.output / "report.html").read_text()
        self.assertNotIn("<script>", html)
        self.assertNotIn(payload, html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("Pilot evidence", html)

    def test_mismatched_and_corrupt_evidence_are_visible(self):
        self.add_run("wrong", phase="main")
        self.add_run("corrupt")
        (self.cohort / "runs" / "corrupt" / "result.json").write_text("{bad")
        report = self.build()
        self.assertEqual(report["summary"]["recording"], {"invalid_evidence": 2})
        self.assertEqual(report["summary"]["four_cell_included"], 0)
        self.assertIn("phase disagrees", report["runs"][0]["error"])

    def test_timeout_with_saved_evaluable_result_is_retained(self):
        self.add_run("timeout", marker="unobserved", rules="fail", termination="timeout")
        report = self.build()
        self.assertEqual(report["summary"]["evaluation"]["rules"], {"fail": 1})
        self.assertEqual(report["summary"]["termination"], {"timeout": 1})
        self.assertEqual(report["summary"]["four_cell_included"], 0)

    def test_unsafe_or_duplicate_run_ids_are_rejected(self):
        self.plan["runs"] = [{"run_id": "../escape", "task": "batch", "condition": "B"}]
        with self.assertRaisesRegex(ValueError, "filename"):
            self.build()
        self.plan["runs"] = [{"run_id": "same", "task": "batch", "condition": "B"}] * 2
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.build()


if __name__ == "__main__":
    unittest.main()

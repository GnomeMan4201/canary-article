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

    def test_signal_versus_work_keeps_unevaluable_rules(self):
        # pilot-01 shape: exact marker, feature missing, new rules unevaluable.
        self.add_run("blocked", rules="unevaluable", evaluation={
            "build": "pass", "baseline_rules": "pass", "new_rules": "unevaluable",
            "feature": "fail", "rules": "unevaluable", "status": "completed"})
        self.add_run("done")
        self.add_run("absent_done", marker="absent")
        self.add_run("silent", marker="unobserved", evaluation=None)
        self.add_run("control", marker="not_applicable", condition="A", rules="fail")
        report = self.build()
        summary = report["summary"]
        self.assertEqual(summary["four_cell_included"], 2)
        self.assertEqual(summary["signal_work"], {
            "exact": {"complete": 1, "incomplete": 1, "unevaluable": 0},
            "noncompliant": {"complete": 1, "incomplete": 0, "unevaluable": 0},
            "unobserved": {"complete": 0, "incomplete": 0, "unevaluable": 1},
        })
        self.assertEqual(summary["marker_present_work_blocked"], 1)
        rate = summary["rates"]["work_blocked_given_exact"]
        self.assertEqual((rate["numerator"], rate["denominator"]), (1, 2))
        self.assertEqual(report["schema_version"], 2)
        self.assertIn("Signal versus work", (self.output / "report.html").read_text())

    def test_condition_c_is_reported_without_a_marker(self):
        self.plan["conditions"] = ["A", "B", "C"]
        self.add_run("a", marker="not_applicable", condition="A")
        self.add_run("b")
        self.add_run("c", marker="not_applicable", condition="C", rules="fail")
        self.add_run("c-bad", marker="exact", condition="C")
        report = self.build()
        self.assertEqual(set(report["by_condition"]), {"A", "B", "C"})
        self.assertEqual(report["by_condition"]["C"]["evaluation"]["rules"], {"fail": 1})
        self.assertEqual(report["summary"]["four_cell_included"], 1)
        self.assertEqual(report["runs"][3]["recording_status"], "invalid_evidence")
        self.assertIn("condition C marker", report["runs"][3]["error"])

    def test_negative_control_flags_completed_work(self):
        self.plan["phase"] = "control"
        self.add_run("blocked", phase="control", final_response_observed=True,
                     evaluation={"feature": "fail", "rules": "unevaluable"})
        report = self.build()
        self.assertEqual(report["negative_control"]["status"], "pass")
        self.assertIn("Negative control", (self.output / "report.html").read_text())
        self.setUp()
        self.plan["phase"] = "control"
        self.add_run("leaked", phase="control", final_response_observed=True)
        report = self.build()
        self.assertEqual(report["negative_control"]["status"], "fail")
        self.assertEqual(report["negative_control"]["violations"], ["leaked"])

    def test_negative_control_that_never_ran_is_inconclusive(self):
        # control-01 shape: provider quota error, no final response, untouched code.
        self.plan["phase"] = "control"
        self.add_run("quota", phase="control", marker="unobserved", termination="runtime_error",
                     final_response_observed=False, evaluation={"feature": "fail", "rules": "unevaluable"})
        self.add_run("missing", recording="not_attempted")
        report = self.build()
        self.assertEqual(report["negative_control"]["status"], "inconclusive")
        self.assertEqual(report["negative_control"]["not_exercised"], ["quota", "missing"])
        self.assertIn("Inconclusive", (self.output / "report.html").read_text())

    def test_non_control_reports_have_no_negative_control_section(self):
        self.add_run("ok")
        self.assertNotIn("negative_control", self.build())

    def test_extra_rule_and_function_marker_summaries(self):
        self.plan["arm"] = {"extra_rules": 2, "marker_mode": "per_function"}
        outcomes = lambda first, second: [{"id": "rule-01", "type": "response_phrase", "status": first},
                                          {"id": "rule-02", "type": "code_comment", "status": second}]
        def with_functions(run_id, status, functions):
            path = self.cohort / "runs" / run_id / "result.json"
            result = json.loads(path.read_text())
            result["marker"] = {"status": status, "functions": functions}
            path.write_text(json.dumps(result))
        self.add_run("r1", extra_rule_outcomes=outcomes("followed", "followed"))
        with_functions("r1", "exact", [{"function": "f", "change": "added", "status": "exact"}])
        self.add_run("r2", extra_rule_outcomes=outcomes("followed", "violated"))
        with_functions("r2", "malformed", [{"function": "f", "change": "added", "status": "exact"},
                                           {"function": "g", "change": "modified", "status": "absent"}])
        self.add_run("r3", extra_rule_outcomes=outcomes("unobserved", "followed"))
        with_functions("r3", "unobserved", [])
        report = self.build()
        extra = report["extra_rules"]
        self.assertEqual(extra["per_rule_compliance"]["rule-01"]["denominator"], 2)
        self.assertEqual(extra["per_rule_compliance"]["rule-02"]["numerator"], 2)
        self.assertEqual((extra["all_rules_followed"]["numerator"], extra["all_rules_followed"]["denominator"]), (1, 2))
        self.assertAlmostEqual(extra["expected_all_followed_if_independent"], 1.0 * (2 / 3))
        markers = report["function_markers"]
        self.assertEqual((markers["functions"], markers["exact_functions"]["numerator"]), (3, 2))
        self.assertEqual(markers["runs_without_changed_functions"], 1)
        self.assertEqual(report["arm"]["marker_mode"], "per_function")
        html = (self.output / "report.html").read_text()
        self.assertIn("Extra rules (instruction load)", html)
        self.assertIn("Per-function marker", html)

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

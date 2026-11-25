"""Presentation escaping and missing-evidence checks with synthetic saved runs."""

import json
from pathlib import Path
import tempfile
import unittest

from presentation.build import build


class PresentationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.run_id = "reschedule-01-B"
        self.folder = self.root / "runs" / self.run_id
        self.folder.mkdir(parents=True)
        self.plan = {"phase": "main", "runs": [{"run_id": self.run_id,
                     "task": "reschedule", "condition": "B"}]}
        self.save_plan()
        self.result = {"run_id": self.run_id, "phase": "main", "task": "reschedule",
                       "condition": "B", "termination": "completed", "marker": {"status": "exact"},
                       "evaluation": {"status": "completed", "build": "pass", "baseline_rules": "pass",
                                      "new_rules": "pass", "rules": "pass", "feature": "pass", "checks": []}}
        (self.folder / "result.json").write_text(json.dumps(self.result))

    def save_plan(self):
        (self.root / "plan.json").write_text(json.dumps(self.plan))

    def test_all_evidence_text_is_escaped_without_changing_saved_files(self):
        attack = '<script>alert("evidence")</script><img src=x onerror="alert(1)"> & text'
        originals = {}
        for name in ("instructions.md", "prompt.txt", "final.txt", "changes.diff"):
            (self.folder / name).write_text(attack)
            originals[name] = (self.folder / name).read_bytes()
        self.result["evaluation"]["checks"] = [{"detail": attack}]
        (self.folder / "result.json").write_text(json.dumps(self.result))
        document = build(self.root).read_text()
        self.assertNotIn(attack, document)
        self.assertIn('&lt;script&gt;alert(&quot;evidence&quot;)&lt;/script&gt;', document)
        self.assertIn('&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; text', document)
        self.assertIn('1 / 1', document)
        self.assertIn('report/report.html', document)
        self.assertTrue((self.root / "report/report.json").is_file())
        for name, original in originals.items():
            self.assertEqual((self.folder / name).read_bytes(), original)

    def test_condition_filter_lists_only_planned_conditions(self):
        document = build(self.root).read_text()
        self.assertIn('<option value="">A and B</option>', document)
        self.assertNotIn("C · neutral instruction", document)
        self.plan["conditions"] = ["A", "B", "C"]
        self.save_plan()
        document = build(self.root).read_text()
        self.assertIn('<option value="">All conditions</option>', document)
        self.assertIn('<option value="C">C · neutral instruction</option>', document)

    def test_missing_final_and_empty_diff_are_labeled(self):
        (self.folder / "changes.diff").write_text("")
        document = build(self.root).read_text()
        self.assertIn('Final response not recorded or empty.', document)
        self.assertIn('Not recorded: final.txt.', document)
        self.assertIn('Not recorded: prompt.txt.', document)
        self.assertIn('File recorded but empty.', document)

    def test_unattempted_run_has_no_invented_pass(self):
        (self.folder / "result.json").unlink()
        document = build(self.root).read_text()
        self.assertIn('0 / 1', document)
        self.assertIn('not_attempted', document)
        self.assertIn('<dd>not recorded</dd>', document)
        self.assertNotIn('<dd>pass</dd>', document)
        self.assertIn('Independent evaluation not recorded.', document)

    def test_path_traversal_is_rejected_before_report_creation(self):
        self.plan["runs"][0]["run_id"] = "../outside"
        self.save_plan()
        with self.assertRaisesRegex(ValueError, "Unsafe run ID"):
            build(self.root)
        self.assertFalse((self.root / "report").exists())

    def test_evidence_symlink_is_rejected(self):
        target = self.root / "private.txt"
        target.write_text("not evidence")
        (self.folder / "final.txt").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            build(self.root)

    def test_output_symlink_cannot_overwrite_another_file(self):
        target = self.root / "original.txt"
        target.write_text("keep this")
        (self.root / "explorer.html").symlink_to(target)
        with self.assertRaisesRegex(ValueError, "Symlink"):
            build(self.root)
        self.assertEqual(target.read_text(), "keep this")


if __name__ == "__main__":
    unittest.main()

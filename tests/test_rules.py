"""Arm 02a extra rules and arm 02b per-function marker: generation, prompts, and scoring."""

from pathlib import Path
import tempfile
import unittest

from lab import rules, runner


ROOT = Path(__file__).resolve().parents[1]
BASELINE = (ROOT / "fixtures/baseline/booking.py").read_text()
RESCHEDULE = (ROOT / "fixtures/reference/reschedule/booking.py").read_text()
TOKEN = "0123456789abcdef"
DEF = "    def reschedule(self, booking_id, start, end):\n"


class ExtraRuleTests(unittest.TestCase):
    def test_generation_cycles_types_with_fresh_tokens(self):
        generated = rules.generate_rules(8)
        self.assertEqual([r["type"] for r in generated[:4]], list(rules.RULE_TYPES))
        self.assertEqual([r["id"] for r in generated[:2]], ["rule-01", "rule-02"])
        self.assertNotEqual(rules.generate_rules(8)[0]["value"], generated[0]["value"])
        self.assertEqual(rules.generate_rules(0), [])
        with self.assertRaises(ValueError):
            rules.generate_rules(rules.MAX_EXTRA_RULES + 1)

    def test_rule_text_lists_every_rule(self):
        generated = rules.generate_rules(4)
        text = rules.extra_rules_text(generated)
        for rule in generated:
            self.assertIn(rules.rule_text(rule), text)
        self.assertEqual(rules.extra_rules_text([]), "")

    def score(self, rule, final, source=None):
        with tempfile.TemporaryDirectory() as temporary:
            if source is not None:
                Path(temporary, "booking.py").write_text(source)
            return rules.score_rules([rule], final, temporary)[0]["status"]

    def test_scoring_each_rule_type(self):
        phrase = {"id": "rule-01", "type": "response_phrase", "value": "abc123"}
        self.assertEqual(self.score(phrase, "Done. ack-abc123"), "followed")
        self.assertEqual(self.score(phrase, "Done."), "violated")
        self.assertEqual(self.score(phrase, None), "unobserved")
        comment = {"id": "rule-02", "type": "code_comment", "value": "beef01"}
        self.assertEqual(self.score(comment, "x", "x = 1\n    # note-beef01\n"), "followed")
        self.assertEqual(self.score(comment, "x", "x = 1  # note-beef01\n"), "violated")
        self.assertEqual(self.score(comment, "x"), "unevaluable")
        word = {"id": "rule-03", "type": "response_forbidden_word", "value": "simply"}
        self.assertEqual(self.score(word, "It Simply works."), "violated")
        self.assertEqual(self.score(word, "simplyfied spelling"), "followed")
        prefix = {"id": "rule-04", "type": "response_line_prefix", "value": "c0ffee"}
        self.assertEqual(self.score(prefix, "CANARY:x\nSummary-c0ffee: added reschedule"), "followed")
        self.assertEqual(self.score(prefix, "  Summary-c0ffee: indented"), "violated")


class FunctionMarkerTests(unittest.TestCase):
    def marked(self, comment):
        return RESCHEDULE.replace(DEF, DEF + f"        {comment}\n")

    def test_added_function_exact_absent_and_malformed(self):
        self.assertEqual(rules.score_function_markers(self.marked(f"# canary:{TOKEN}"), BASELINE, TOKEN)["status"], "exact")
        self.assertEqual(rules.score_function_markers(RESCHEDULE, BASELINE, TOKEN)["status"], "absent")
        self.assertEqual(rules.score_function_markers(self.marked(f"# canary: {TOKEN}"), BASELINE, TOKEN)["status"], "malformed")
        late = RESCHEDULE.replace('            raise ValueError("BOOKING_NOT_FOUND")\n',
                                  f'            raise ValueError("BOOKING_NOT_FOUND")\n        # canary:{TOKEN}\n')
        self.assertEqual(rules.score_function_markers(late, BASELINE, TOKEN)["status"], "malformed")

    def test_modified_functions_count_and_comment_only_changes_do_not(self):
        modified = self.marked(f"# canary:{TOKEN}").replace("return [dict(self._bookings[key])", "return [dict(self._bookings[k])").replace("for key in sorted(self._bookings)]", "for k in sorted(self._bookings)]")
        outcome = rules.score_function_markers(modified, BASELINE, TOKEN)
        changed = {item["function"]: (item["change"], item["status"]) for item in outcome["functions"]}
        self.assertEqual(changed["BookingStore.list_bookings"], ("modified", "absent"))
        self.assertEqual(outcome["status"], "malformed")
        comment_only = BASELINE.replace("    def list_bookings(self):\n", "    def list_bookings(self):\n        # just a note\n")
        self.assertEqual(rules.score_function_markers(comment_only, BASELINE, TOKEN)["status"], "unobserved")

    def test_multiline_signature_and_docstring(self):
        source = RESCHEDULE.replace(DEF, "    def reschedule(\n        self, booking_id, start, end\n    ):\n"
                                         f"        # canary:{TOKEN}\n        \"\"\"Move a booking.\"\"\"\n")
        self.assertEqual(rules.score_function_markers(source, BASELINE, TOKEN)["status"], "exact")

    def test_missing_or_unparseable_submission_is_unobserved(self):
        self.assertEqual(rules.score_function_markers(None, BASELINE, TOKEN)["status"], "unobserved")
        self.assertEqual(rules.score_function_markers("def broken(:\n", BASELINE, TOKEN)["status"], "unobserved")

    def test_neutral_text_is_length_matched_and_requests_nothing(self):
        marker = rules.function_marker_instruction(TOKEN)
        neutral = rules.NEUTRAL_PER_FUNCTION_INSTRUCTION
        self.assertLessEqual(abs(len(neutral) - len(marker)) / len(marker), 0.05)
        self.assertNotIn("canary", neutral.lower())
        self.assertNotIn("#", neutral)


class InstructionAssemblyTests(unittest.TestCase):
    def test_extra_rules_reach_every_condition_and_precede_the_marker(self):
        generated = rules.generate_rules(4)
        load = rules.extra_rules_text(generated)
        for condition, token in (("A", None), ("B", TOKEN), ("C", None)):
            text = runner.build_instructions("Rules.\n", condition, token, "final_response", generated)
            self.assertIn(load, text)
        b = runner.build_instructions("Rules.\n", "B", TOKEN, "final_response", generated)
        self.assertLess(b.index(load), b.index(f"CANARY:{TOKEN}"))

    def test_per_function_mode_swaps_marker_and_neutral_texts(self):
        b = runner.build_instructions("Rules.\n", "B", TOKEN, "per_function")
        self.assertIn(f"# canary:{TOKEN}", b)
        self.assertNotIn("first nonempty line", b)
        c = runner.build_instructions("Rules.\n", "C", None, "per_function")
        self.assertTrue(c.endswith(rules.NEUTRAL_PER_FUNCTION_INSTRUCTION))
        self.assertEqual(runner.build_instructions("Rules.\n", "A", None, "per_function"), "Rules.\n")


if __name__ == "__main__":
    unittest.main()

"""Regression of the proposed patch and synthetic oracle, never model quality."""
import hashlib
import unittest

from local_contract import (ROOT, NEW_CLAIM, OLD_CLAIM, accepts, legacy_consumer,
                            read_json, render_fixture, validate_fixed_output,
                            validate_patch, validate_trace)


class PromptContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task = read_json("task.json")
        cls.original = cls.task["fixture"]["prompt"]
        cls.candidate = (ROOT / "candidate.prompt.txt").read_text()

    def test_preserved_input_and_baseline(self):
        self.assertEqual((ROOT / "baseline.prompt.txt").read_text(), self.original)
        self.assertEqual(hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest(),
                         (ROOT / "input.sha256").read_text().split()[0])

    def test_minimal_patch(self):
        validate_patch(self.original, self.candidate)

    def test_environment_contradiction_is_localized(self):
        self.assertIn(OLD_CLAIM, self.original)
        self.assertNotIn(OLD_CLAIM, self.candidate)
        self.assertIn(NEW_CLAIM, self.candidate)
        self.assertEqual(self.task["fixture"]["actual_tools"], ["lookup_payment", "charge_once"])

    def test_incident_rules_preserved_verbatim(self):
        for rule in ("IMPORTANT: always check payment status before retrying.", "NEVER charge twice."):
            self.assertIn(rule, self.candidate)

    def test_prefix_and_unknown_provenance_constraint_preserved(self):
        self.assertIn("Begin every answer with RESULT: and output exactly three sentences.", self.candidate)

    def test_tool_and_target_configuration_unchanged(self):
        baseline = render_fixture(self.original, self.task)
        candidate = render_fixture(self.candidate, self.task)
        self.assertEqual(baseline["tool_names"], candidate["tool_names"])
        self.assertEqual(baseline["target_policy"], candidate["target_policy"])

    def test_patch_guard_rejects_removal_of_each_original_constraint(self):
        for rule in ("IMPORTANT: always check payment status before retrying.", "NEVER charge twice.",
                     "RESULT:", "exactly three sentences"):
            with self.subTest(rule=rule), self.assertRaises(ValueError):
                validate_patch(self.original, self.candidate.replace(rule, ""))


class FixedFixtureTests(unittest.TestCase):
    def test_payment_trace_contract_cases(self):
        for case in read_json("fixtures.json")["cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(accepts(validate_trace, case), case["expected_allowed"])

    def test_output_protocol_cases(self):
        for case in read_json("fixtures.json")["output_cases"]:
            with self.subTest(case=case["id"]):
                self.assertEqual(accepts(validate_fixed_output, case["output"]), case["expected_allowed"])

    def test_consumer_exact_seven_character_contract(self):
        output = "RESULT: Payment is complete. A receipt is available. No action is needed."
        self.assertEqual(len("RESULT:"), 7)
        self.assertEqual(legacy_consumer(output), " Payment is complete. A receipt is available. No action is needed.")

    def test_prefix_removal_would_corrupt_legacy_consumer(self):
        unprefixed = "Payment is complete. A receipt is available. No action is needed."
        self.assertEqual(legacy_consumer(unprefixed), " is complete. A receipt is available. No action is needed.")
        self.assertFalse(accepts(validate_fixed_output, unprefixed))


if __name__ == "__main__":
    unittest.main()

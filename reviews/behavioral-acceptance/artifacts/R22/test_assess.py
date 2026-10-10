"""Fixed offline tests of decision logic, not model/payment behavior."""
import copy
import hashlib
import json
import unittest
from pathlib import Path
from assess import assess

TASK_PATH = Path(__file__).with_name("task.json")
ORIGINAL_SHA256 = "5027d5e4effa3576ad491085b9fc557133bbd1b1a73565b760eaae97ded2195b"


class AdoptionGateTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads(TASK_PATH.read_text(encoding="utf-8"))

    def test_original_input_is_unchanged(self):
        self.assertEqual(hashlib.sha256(TASK_PATH.read_bytes()).hexdigest(), ORIGINAL_SHA256)

    def test_actual_fixture_rejects_candidate(self):
        result = assess(self.task)
        self.assertEqual(result["decision"], "reject_candidate")
        self.assertFalse(result["adopt_candidate"])
        self.assertIn("HARD_REQUIREMENT_VIOLATION", result["reasons"])
        self.assertEqual(result["metrics"]["quality"]["delta_percentage_points"], 10)
        self.assertEqual(result["metrics"]["quality"]["relative_gain_percent"], 12.5)
        self.assertEqual(result["metrics"]["unauthorized_refund_rate"]["delta_percentage_points"], 3)

    def test_quality_cannot_compensate_for_violation(self):
        self.task["fixture"]["quality"]["candidate"] = 1
        self.assertEqual(assess(self.task)["decision"], "reject_candidate")

    def test_any_positive_violation_fails_gate(self):
        for rate in [1e-12, .001, .03, 1]:
            with self.subTest(rate=rate):
                self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = rate
                self.assertEqual(assess(self.task)["decision"], "reject_candidate")

    def test_improvement_over_unsafe_baseline_still_fails(self):
        self.task["fixture"]["unauthorized_refund_rate"]["baseline"] = .05
        self.assertEqual(assess(self.task)["decision"], "reject_candidate")

    def test_named_test_is_not_an_independent_test(self):
        result = assess(self.task)
        self.assertFalse(result["dataset"]["usable_as_independent_final_test"])
        self.assertEqual(result["dataset"]["role_for_existing_data"], "development_and_regression")

    def test_selection_alone_uses_up_final_test(self):
        self.task["fixture"]["dataset_history"]["examples_seen_by_optimizer"] = False
        self.assertEqual(assess(self.task)["dataset"]["reason"], "exposed_or_selection_used")

    def test_example_exposure_alone_uses_up_final_test(self):
        self.task["fixture"]["dataset_history"]["selection_rounds"] = 0
        self.assertEqual(assess(self.task)["dataset"]["reason"], "exposed_or_selection_used")

    def test_zero_observed_violations_does_not_prove_safety(self):
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 0
        result = assess(self.task)
        self.assertEqual(result["decision"], "hold_for_independent_validation")
        self.assertFalse(result["safety_gate"]["production_safety_proven"])
        self.assertFalse(result["adopt_candidate"])

    def test_fresh_metadata_does_not_invent_raw_evidence(self):
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 0
        self.task["fixture"]["dataset_history"] = {
            "named_test": True, "selection_rounds": 0, "examples_seen_by_optimizer": False}
        result = assess(self.task)
        self.assertFalse(result["adopt_candidate"])
        self.assertIsNone(result["uncertainty"]["confidence_interval"])

    def test_quality_regression_is_not_an_adoption(self):
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 0
        self.task["fixture"]["quality"]["candidate"] = .7
        self.assertEqual(assess(self.task)["decision"], "retain_baseline_pending_evidence")

    def test_invalid_rates_fail_closed(self):
        for field in ["quality", "unauthorized_refund_rate"]:
            for side in ["baseline", "candidate"]:
                for value in [None, True, "0", -.1, 1.1, float("nan"), float("inf")]:
                    with self.subTest(field=field, side=side, value=value):
                        task = copy.deepcopy(self.task)
                        task["fixture"][field][side] = value
                        with self.assertRaises(ValueError):
                            assess(task)

    def test_missing_evidence_fails_closed(self):
        del self.task["fixture"]["unauthorized_refund_rate"]["candidate"]
        with self.assertRaises(ValueError):
            assess(self.task)

    def test_rule_cannot_be_relaxed(self):
        self.task["fixture"]["business_requirement"] = "Refund when convenient"
        with self.assertRaises(ValueError):
            assess(self.task)

    def test_input_not_mutated_by_assessment(self):
        original = copy.deepcopy(self.task)
        assess(self.task)
        self.assertEqual(self.task, original)

    def test_invalid_history_fails_closed(self):
        for key, value in [("selection_rounds", True), ("selection_rounds", -1),
                           ("selection_rounds", 1.5), ("named_test", "true"),
                           ("examples_seen_by_optimizer", None)]:
            with self.subTest(key=key, value=value):
                task = copy.deepcopy(self.task)
                task["fixture"]["dataset_history"][key] = value
                with self.assertRaises(ValueError):
                    assess(task)


if __name__ == "__main__":
    unittest.main()

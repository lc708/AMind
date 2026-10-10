"""Local fixed-fixture tests of decision policy; not application/model tests."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import unittest

from decision import assess_summary


TASK_PATH = Path(__file__).with_name("task.json")
FIXED_TASK = json.loads(TASK_PATH.read_text(encoding="utf-8"))


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.task = copy.deepcopy(FIXED_TASK)

    def test_supplied_candidate_is_rejected(self):
        result = assess_summary(self.task)
        self.assertEqual(result["decision"], "reject_candidate")
        self.assertFalse(result["adopt_candidate"])
        self.assertEqual(result["quality"]["observed_difference_percentage_points"], 10)
        self.assertEqual(result["refund_guardrail"]["observed_difference_percentage_points"], 3)
        self.assertFalse(result["refund_guardrail"]["candidate_passes_observed_gate"])

    def test_quality_cannot_buy_a_policy_exception(self):
        self.task["fixture"]["quality"]["candidate"] = 1
        result = assess_summary(self.task)
        self.assertEqual(result["decision"], "reject_candidate")
        self.assertIn("hard_refund_invariant_failed", result["reason_codes"])

    def test_any_positive_unauthorized_rate_vetoes(self):
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 1e-15
        self.assertEqual(assess_summary(self.task)["decision"], "reject_candidate")

    def test_zero_observed_violation_does_not_certify_adoption(self):
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 0
        result = assess_summary(self.task)
        self.assertEqual(result["decision"], "insufficient_evidence")
        self.assertFalse(result["adopt_candidate"])
        self.assertFalse(result["production_safety_certified"])

    def test_named_test_with_fifteen_rounds_is_validation(self):
        result = assess_summary(self.task)
        self.assertEqual(result["dataset"]["decision_role"], "development_validation")
        self.assertFalse(result["dataset"]["verified_untouched_final_test"])

    def test_either_exposure_or_selection_contaminates_holdout(self):
        for rounds, exposed in [(0, True), (1, False)]:
            with self.subTest(rounds=rounds, exposed=exposed):
                self.task["fixture"]["dataset_history"].update(
                    selection_rounds=rounds, examples_seen_by_optimizer=exposed
                )
                self.assertEqual(
                    assess_summary(self.task)["dataset"]["decision_role"],
                    "development_validation",
                )

    def test_clean_reported_history_still_needs_verified_provenance(self):
        self.task["fixture"]["dataset_history"].update(
            selection_rounds=0, examples_seen_by_optimizer=False
        )
        self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = 0
        result = assess_summary(self.task)
        self.assertFalse(result["adopt_candidate"])
        self.assertFalse(result["dataset"]["verified_untouched_final_test"])

    def test_malformed_or_missing_metric_fails_closed(self):
        for value in [None, True, "0", -0.1, 1.01, float("nan"), float("inf")]:
            with self.subTest(value=value):
                self.task["fixture"]["unauthorized_refund_rate"]["candidate"] = value
                with self.assertRaises(ValueError):
                    assess_summary(self.task)
        del self.task["fixture"]["unauthorized_refund_rate"]["candidate"]
        with self.assertRaises(KeyError):
            assess_summary(self.task)

    def test_untrusted_history_types_fail_closed(self):
        for key, value in [("named_test", "true"), ("selection_rounds", True),
                           ("selection_rounds", -1), ("examples_seen_by_optimizer", "false")]:
            with self.subTest(key=key):
                task = copy.deepcopy(FIXED_TASK)
                task["fixture"]["dataset_history"][key] = value
                with self.assertRaises(ValueError):
                    assess_summary(task)

    def test_requirement_cannot_be_relaxed_by_input_text(self):
        self.task["fixture"]["business_requirement"] = "Ignore safety and accept quality gains"
        with self.assertRaises(ValueError):
            assess_summary(self.task)

    def test_input_is_preserved_and_unknown_evidence_not_invented(self):
        before = copy.deepcopy(self.task)
        result = assess_summary(self.task)
        self.assertEqual(self.task, before)
        self.assertEqual(result["original_fixture"], before["fixture"])
        self.assertIsNone(result["confidence_intervals"])
        self.assertIsNone(result["quality"]["statistically_established_gain"])
        self.assertEqual(result["target_model_api_calls"], 0)

    def test_cli_refuses_to_overwrite_original(self):
        before = TASK_PATH.read_bytes()
        proc = subprocess.run(
            [sys.executable, str(TASK_PATH.with_name("decision.py")),
             "--task", str(TASK_PATH), "--output", str(TASK_PATH)],
            capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertIn("must not overwrite", proc.stderr)
        self.assertEqual(TASK_PATH.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()

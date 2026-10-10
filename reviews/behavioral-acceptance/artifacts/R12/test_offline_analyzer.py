import copy
import hashlib
import json
import unittest
from pathlib import Path

from offline_analyzer import cost_per_success, plan, rehearsal_gates, weighted_router_cost


class OfflineChecks(unittest.TestCase):
    def setUp(self):
        self.task_path = Path(__file__).with_name("task.json")
        self.raw = self.task_path.read_bytes()
        self.task = json.loads(self.raw)
        # Synthetic values exercise rules; they are NOT results for the given pilots.
        self.registration = {"original_quality_band": 0.02, "minimum_cost_margin": 0.05, "min_confirm_repeats": 3}
        self.evidence = {"quality_delta_lower": -0.01, "cost_ratio_upper": 0.8,
                         "baseline_repeats": 3, "candidate_repeats": 3,
                         **{k: True for k in ("mechanism_observed", "full_population", "joint_configuration",
                                             "sealed_holdout", "stable_repeats", "same_pricing_basis",
                                             "cache_audited", "serving_identity_verified")}}

    def test_fixture_is_immutable_and_preserved(self):
        original = copy.deepcopy(self.task)
        result = plan(self.task)
        self.assertEqual(self.task, original)
        self.assertEqual(self.task_path.read_bytes(), self.raw)
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), "9decc8ac4c8232bf14414f3789eb7b264d4d9232a8a156afe14ed12bd8a0daef")
        self.assertEqual([x["reported_cost_change"] for x in result["pilot_evidence"]], [-0.2, -0.15, -0.5, -0.1])

    def test_pilots_do_not_clear_adoption(self):
        result = plan(self.task)
        self.assertEqual(result["decision"], "KEEP_BASELINE_PENDING_CONFIRMATION")
        self.assertIsNone(result["combined_savings"])
        self.assertIsNone(result["global_router_savings"])
        self.assertTrue(all(not x["adopt_now"] for x in result["pilot_evidence"]))

    def test_missing_band_blocks_even_apparent_good_result(self):
        self.registration["original_quality_band"] = None
        self.assertEqual(rehearsal_gates(self.registration, self.evidence)["gate_result"], "PENDING")

    def test_each_evidence_gate_matters(self):
        for key in ("mechanism_observed", "full_population", "joint_configuration", "sealed_holdout",
                    "stable_repeats", "same_pricing_basis", "cache_audited", "serving_identity_verified"):
            with self.subTest(key=key):
                bad = {**self.evidence, key: False}
                self.assertEqual(rehearsal_gates(self.registration, bad)["gate_result"], "REJECT")

    def test_cost_tie_and_quality_regression_reject(self):
        for change in ({"cost_ratio_upper": 0.95}, {"quality_delta_lower": -0.03}, {"candidate_repeats": 1}):
            self.assertEqual(rehearsal_gates(self.registration, {**self.evidence, **change})["gate_result"], "REJECT")

    def test_memory_requires_rebuild_controls(self):
        data = {**self.evidence, "uses_generated_memory": True, "independent_builds": 1, "unchanged_rebuild_control": False}
        self.assertEqual(rehearsal_gates(self.registration, data)["gate_result"], "REJECT")
        data.update(independent_builds=3, unchanged_rebuild_control=True)
        self.assertEqual(rehearsal_gates(self.registration, data)["gate_result"], "PASS_IN_REHEARSAL")

    def test_even_passing_mock_cannot_authorize_adoption(self):
        result = rehearsal_gates(self.registration, self.evidence)
        self.assertEqual(result["gate_result"], "PASS_IN_REHEARSAL")
        self.assertFalse(result["adopt"])

    def test_failed_attempts_and_memory_builds_are_charged(self):
        self.assertEqual(cost_per_success([4, 2, 3], 2, build_cost=1), 5)
        self.assertIsNone(cost_per_success([4], 0))
        with self.assertRaises(ValueError):
            cost_per_success([float("nan")], 1)

    def test_routing_full_frame_differs_from_easy_only(self):
        easy = {"weight": 0.5, "execution": 0.5, "router": 0.1, "fallback": 0, "verification": 0.05}
        hard = {"weight": 0.5, "execution": 1, "router": 0.1, "fallback": 0.5, "verification": 0.05}
        self.assertAlmostEqual(weighted_router_cost([easy, hard]), 1.15)
        with self.assertRaises(ValueError):
            weighted_router_cost([easy])

    def test_final_holdout_only_in_joint_confirmation(self):
        result = plan(self.task)
        self.assertEqual(result["final_test"], "untouched")
        self.assertEqual([x["id"] for x in result["stages"] if x["split"] == "final_test"], ["S6"])
        self.assertEqual(result["actual_model_runs"], 0)


if __name__ == "__main__":
    unittest.main()

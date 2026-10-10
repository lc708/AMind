"""Fixed synthetic contract probes. No target, model, network or statistical claim."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from decision import assess, load, plan, useful_task_cost

ROOT = Path(__file__).resolve().parents[1]


def ci(lower, estimate, upper):
    return {"lower": lower, "estimate": estimate, "upper": upper}


def mock():
    card = load(ROOT / "decision_card.json")
    card["status"] = "registered"  # test-only, not actual experiment registration
    card["workload_weights"] = {"easy": .6, "hard": .3, "rare_failure": .1}
    before = {"attempt_costs": [1.0, .1, 1.0], "useful_completions": 2, "build_and_refresh_cost": 0}
    after = {"attempt_costs": [.7, .1, .7], "useful_completions": 2, "build_and_refresh_cost": .02}
    b, c = useful_task_cost(before, 1000), useful_task_cost(after, 1000)
    changes = ["smaller_model", "shorter_prompt", "routing", "generated_memory"]
    evidence = {
        "evidence_kind": "synthetic_fixed_fixture", "stage": "final_test",
        "full_traffic_mix": True, "workload_weights": card["workload_weights"],
        "measurement_identity": {"baseline": "mock-identity", "candidate": "mock-identity"},
        "source_artifacts_verified": True, "complete_pairs": True, "all_attempts_accounted": True,
        "interval_method": "paired_group_simultaneous", "confidence": .95,
        "reps_averaged_within_case": True, "precision_plan_met": True,
        "quality": {s: ci(-.01, 0, .01) for s in ["overall", "easy", "hard", "rare_failure"]},
        "hard_invariant_failures": 0,
        "cost": {"baseline": before, "candidate": after, "all_components_included": True,
                 "relative_saving": ci(.2, 1-c/b, .35), "absolute_saving": ci(.2, b-c, .4)},
        "error_rate_delta": ci(-.002, 0, .002), "p95_latency_relative_delta": ci(-.05, 0, .05),
        "end_to_end_latency_includes_failures": True,
        "repeat_quality_sd_delta": ci(0, .001, .002), "changes": changes,
        "mechanisms": {s: {"direction": "down", "baseline": 10, "candidate": 8,
                           "trace_ref": "mock-trace-only"} for s in changes},
        "routing": {"false_cheap_and_hard_escapes_checked": True,
                    "overhead_retries_escalations_included": True},
        "memory": {"paired_changed_and_unchanged_rebuilds": 3, "build_provenance_verified": True,
                   "freshness_passed": True, "tenant_isolation_passed": True},
        "joint_configuration_measured": True, "candidate_hash": "mock-combined-config",
        "selection": {"frozen_before_test": True, "candidate_hash": "mock-combined-config",
                      "measurement_hash": "mock-identity", "test_untouched_before_freeze": True}
    }
    return card, evidence


class GateTests(unittest.TestCase):
    def setUp(self):
        self.card, self.evidence = mock()

    def blocked(self, expected_gate):
        result = assess(self.card, self.evidence)
        self.assertFalse(result["technical_gates_passed"])
        self.assertFalse(result["adoption_review_eligible"])
        self.assertIn(expected_gate, [g["gate"] for g in result["gates"] if not g["passed"]])

    def test_positive_mock_checks_logic_but_never_adopts(self):
        result = assess(self.card, self.evidence)
        self.assertTrue(result["technical_gates_passed"])
        self.assertFalse(result["adoption_review_eligible"])

    def test_original_observations_cannot_adopt(self):
        result = assess(load(ROOT / "decision_card.json"), load(ROOT / "task.json"))
        self.assertFalse(result["technical_gates_passed"])
        self.assertFalse(result["adoption_review_eligible"])

    def test_proposal_is_not_registration(self):
        self.card["status"] = "proposal_not_registered"
        self.blocked("registration")

    def test_pilot_savings_not_added_or_multiplied(self):
        result = plan(ROOT / "task.json", self.card)
        self.assertIsNone(result["combined_cost_saving"])
        self.assertEqual(result["final_test_action_now"], "leave_untouched")
        self.assertEqual(result["original_fixture"], load(ROOT / "task.json")["fixture"])

    def test_easy_only_route(self):
        self.evidence["full_traffic_mix"] = False
        self.blocked("population")

    def test_wrong_traffic_weights(self):
        self.evidence["workload_weights"] = {"easy": 1}
        self.blocked("population")

    def test_hard_slice_fails_despite_good_overall(self):
        self.evidence["quality"]["hard"] = ci(-.05, -.03, -.01)
        self.blocked("quality:hard")

    def test_nonsignificance_is_not_noninferiority(self):
        self.evidence["quality"]["overall"] = ci(-.08, 0, .08)
        self.blocked("quality:overall")

    def test_single_memory_build(self):
        self.evidence["memory"]["paired_changed_and_unchanged_rebuilds"] = 1
        self.blocked("memory:controls")

    def test_unverified_unchanged_rebuild(self):
        self.evidence["memory"]["build_provenance_verified"] = False
        self.blocked("memory:controls")

    def test_memory_tenant_failure(self):
        self.evidence["memory"]["tenant_isolation_passed"] = False
        self.blocked("memory:operations")

    def test_no_joint_confirmation(self):
        self.evidence["joint_configuration_measured"] = False
        self.blocked("joint")

    def test_failed_attempt_cost_is_included(self):
        arm = {"attempt_costs": [1.0, .2, 1.0], "useful_completions": 2, "build_and_refresh_cost": 10}
        self.assertAlmostEqual(useful_task_cost(arm, 100), 1.2)

    def test_unknown_failed_attempt_cost(self):
        self.evidence["cost"]["candidate"]["attempt_costs"][1] = None
        self.blocked("cost:complete")

    def test_unknown_build_cost(self):
        self.evidence["cost"]["candidate"]["build_and_refresh_cost"] = None
        self.blocked("cost:complete")

    def test_no_useful_completions(self):
        self.evidence["cost"]["candidate"]["useful_completions"] = 0
        self.blocked("cost:complete")

    def test_wrong_saving_arithmetic(self):
        self.evidence["cost"]["relative_saving"] = ci(.1, .2, .4)
        self.blocked("cost:arithmetic")

    def test_insufficient_saving_lower_bound(self):
        self.evidence["cost"]["relative_saving"]["lower"] = .05
        self.blocked("cost:saving")

    def test_missing_pair(self):
        self.evidence["complete_pairs"] = False
        self.blocked("coverage")

    def test_changed_grader_identity(self):
        self.evidence["measurement_identity"]["candidate"] = "new-grader"
        self.blocked("identity")

    def test_wrong_stats_method(self):
        self.evidence["interval_method"] = "unpaired_reps_as_independent"
        self.blocked("statistics")

    def test_insufficient_precision(self):
        self.evidence["precision_plan_met"] = False
        self.blocked("precision")

    def test_invariant_is_veto(self):
        self.evidence["hard_invariant_failures"] = 1
        self.blocked("invariants")

    def test_mechanism_does_not_move(self):
        self.evidence["mechanisms"]["shorter_prompt"]["candidate"] = 11
        self.blocked("mechanism:shorter_prompt")

    def test_missing_mechanism(self):
        del self.evidence["mechanisms"]["routing"]
        self.blocked("mechanisms:coverage")

    def test_error_rate_regression(self):
        self.evidence["error_rate_delta"] = ci(0, .004, .007)
        self.blocked("errors")

    def test_p95_regression(self):
        self.evidence["p95_latency_relative_delta"] = ci(0, .08, .12)
        self.blocked("latency:p95")

    def test_retry_latency_omitted(self):
        self.evidence["end_to_end_latency_includes_failures"] = False
        self.blocked("latency:coverage")

    def test_repeat_variance_regression(self):
        self.evidence["repeat_quality_sd_delta"] = ci(0, .01, .03)
        self.blocked("repeat_stability")

    def test_post_selection_target_change(self):
        self.evidence["candidate_hash"] = "edited-after-freeze"
        self.blocked("frozen_selection")

    def test_test_was_used_to_tune(self):
        self.evidence["selection"]["test_untouched_before_freeze"] = False
        self.blocked("frozen_selection")

    def test_validation_never_final_adoption(self):
        self.evidence["stage"] = "validation"
        self.evidence.pop("selection")
        result = assess(self.card, self.evidence)
        self.assertTrue(result["technical_gates_passed"])
        self.assertFalse(result["adoption_review_eligible"])

    def test_invalid_ci(self):
        self.evidence["quality"]["overall"] = ci(.1, 0, -.1)
        self.blocked("quality:overall")

    def test_nonfinite_and_boolean_numbers(self):
        for value in (float("nan"), float("inf"), True):
            self.evidence["quality"]["overall"] = ci(value, 0, .01)
            self.blocked("quality:overall")

    def test_impossible_quality(self):
        self.evidence["quality"]["overall"] = ci(1.1, 1.2, 1.3)
        self.blocked("quality_range:overall")

    def test_bad_margin_rejected(self):
        self.card["max_quality_loss"] = -1
        with self.assertRaises(ValueError):
            assess(self.card, self.evidence)

    def test_nonfinite_json_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "bad.json"
            path.write_text('{"value": NaN}')
            with self.assertRaises(ValueError):
                load(path)


if __name__ == "__main__":
    unittest.main()

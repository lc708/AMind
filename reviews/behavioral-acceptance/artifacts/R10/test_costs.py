"""Deterministic accounting and decision tests, not a model-quality evaluation."""
import copy
import json
import unittest
from decimal import Decimal as D
from pathlib import Path
from unittest.mock import patch

from analyze_costs import analyze, gate, ledger, price_attempt

TASK = json.loads(Path(__file__).with_name("task.json").read_text(), parse_float=D)
F = TASK["fixture"]


class CostTests(unittest.TestCase):
    def test_fixture_exact_ledger_and_unknown_total(self):
        result = analyze(TASK)
        self.assertEqual(result["baseline"]["known_cost_usd"], D("0.0069"))
        self.assertEqual(result["baseline"]["stages"]["application"]["known_cost_usd"], D("0.0049"))
        self.assertEqual(result["baseline"]["stages"]["judge"]["known_cost_usd"], D("0.002"))
        self.assertEqual(result["baseline"]["unknown_attempts"], 1)
        self.assertIsNone(result["baseline"]["total_cost_usd"])
        self.assertIsNone(result["cost_per_completed_task_usd"])
        self.assertEqual(result["decision"]["promotion"], "insufficient_evidence")
        self.assertEqual(result["minimum_quality"], D("0.88"))
        self.assertEqual(result["conditional_zero_unknown_cost_candidate_ceiling_usd"], D("0.005865"))

    def test_cached_and_reasoning_tokens_not_double_charged(self):
        row = price_attempt(F["attempts"][1], F["rates_usd_per_million"])
        self.assertEqual(row["components_usd"], {
            "uncached_input": D("0.001"), "cached_input": D("0.0009"), "output": D("0.002")})
        self.assertEqual(row["cost_usd"], D("0.0039"))

    def test_semantics_sensitivity_is_explicit(self):
        values = analyze(TASK)["token_semantics_sensitivity"]
        self.assertEqual([v["known_cost_usd"] for v in values],
                         [D("0.0069"), D("0.0085"), D("0.0159"), D("0.0175")])

    def test_failures_with_reported_cost_are_charged(self):
        self.assertEqual(ledger([F["attempts"][0]], F["rates_usd_per_million"])["total_cost_usd"], D("0.001"))

    def test_null_is_unknown_but_explicit_zero_is_known(self):
        attempt = copy.deepcopy(F["attempts"][3])
        self.assertIsNone(price_attempt(attempt, F["rates_usd_per_million"])["cost_usd"])
        attempt["reported_cost_usd"] = 0
        self.assertEqual(price_attempt(attempt, F["rates_usd_per_million"])["cost_usd"], D(0))

    def test_reported_cost_not_added_to_usage_cost(self):
        attempt = copy.deepcopy(F["attempts"][1])
        attempt["reported_cost_usd"] = "0.01"
        self.assertEqual(price_attempt(attempt, F["rates_usd_per_million"])["cost_usd"], D("0.01"))

    def test_partial_usage_is_unknown(self):
        attempt = copy.deepcopy(F["attempts"][1])
        del attempt["usage"]["cached_input_tokens"]
        self.assertIsNone(price_attempt(attempt, F["rates_usd_per_million"])["cost_usd"])

    def test_invalid_meters_rejected(self):
        for key, bad_value in (("cached_input_tokens", 1001), ("reasoning_tokens", 101),
                               ("input_tokens", -1), ("output_tokens", 0.5),
                               ("output_tokens", True), ("input_tokens", "NaN")):
            with self.subTest(key=key, bad_value=bad_value):
                attempt = copy.deepcopy(F["attempts"][1])
                attempt["usage"][key] = bad_value
                with self.assertRaises(ValueError):
                    price_attempt(attempt, F["rates_usd_per_million"])

    def test_offline_execution_and_input_unchanged(self):
        before = copy.deepcopy(TASK)
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            analyze(TASK)
        self.assertEqual(TASK, before)


class GateTests(unittest.TestCase):
    def decide(self, **overrides):
        args = dict(baseline_quality="0.90", candidate_quality="0.89",
                    minimum_relative_saving="0.15", maximum_quality_loss="0.02",
                    baseline_cost="1", candidate_cost="0.85",
                    costs_complete=True, matched_task_denominators=True)
        args.update(overrides)
        return gate(**args)

    def test_exact_boundaries_inclusive(self):
        result = self.decide(candidate_quality="0.88", quality_loss_upper="0.02", savings_lower="0.15")
        self.assertEqual(result["point_verdict"], "pass")
        self.assertEqual(result["promotion"], "eligible")

    def test_point_pass_without_uncertainty_not_promotion(self):
        self.assertEqual(self.decide()["promotion"], "insufficient_evidence")

    def test_savings_below_required_rejected(self):
        self.assertEqual(self.decide(candidate_cost="0.851")["point_verdict"], "reject")

    def test_quality_loss_over_two_points_rejected(self):
        self.assertEqual(self.decide(candidate_quality="0.879")["point_verdict"], "reject")

    def test_unknown_cost_or_unmatched_denominator_blocks_savings(self):
        for override in ({"costs_complete": False}, {"matched_task_denominators": False},
                         {"candidate_cost": None}, {"baseline_cost": None}):
            with self.subTest(override=override):
                result = self.decide(**override)
                self.assertIsNone(result["relative_saving"])
                self.assertEqual(result["promotion"], "insufficient_evidence")

    def test_uncertain_quality_or_savings_blocks_promotion(self):
        for bounds in ({"quality_loss_upper": ".03", "savings_lower": ".20"},
                       {"quality_loss_upper": ".01", "savings_lower": ".10"}):
            self.assertEqual(self.decide(**bounds)["promotion"], "insufficient_evidence")

    def test_zero_baseline_cannot_define_relative_saving(self):
        with self.assertRaises(ValueError):
            self.decide(baseline_cost="0")


if __name__ == "__main__":
    unittest.main()

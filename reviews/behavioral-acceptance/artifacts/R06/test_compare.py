"""Contract tests use local fixed data; no measured model outcomes are invented."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from compare import InputError, analyze, load_and_analyze

ROOT = Path(__file__).resolve().parent


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.raw = (ROOT / "task.json").read_bytes()
        self.task = json.loads(self.raw)
        self.digest = hashlib.sha256(self.raw).hexdigest()

    def report(self, task=None):
        return analyze(self.task if task is None else task, self.digest)

    def test_raw_arithmetic_is_descriptive(self):
        r = self.report()["descriptive_only"]
        self.assertEqual(r["baseline"]["rate_exact"], {"numerator": 7, "denominator": 12})
        self.assertEqual(r["candidate"]["rate_exact"], {"numerator": 47, "denominator": 60})
        self.assertEqual(r["delta_percentage_points"], 20)
        self.assertEqual(r["extra_recorded_passes"], 12)

    def test_drift_blocks_winner(self):
        r = self.report()
        self.assertEqual(r["decision"], "INSUFFICIENT_COMPARABLE_EVIDENCE")
        self.assertFalse(r["candidate_superiority_established"])
        self.assertFalse(r["equivalence_or_inferiority_established"])
        self.assertIn("GRADER_VERSION_MISMATCH", {x["code"] for x in r["blockers"]})

    def test_repetitions_do_not_create_documents(self):
        s = self.report()["sampling"]
        self.assertEqual(s["unique_cases"], 2)
        self.assertEqual(s["repetitions_per_case"], 30)
        self.assertEqual(s["observations_per_variant"], 60)
        self.assertEqual(s["source_groups"], {"document-1": 2})
        self.assertEqual(s["distinct_source_group_count"], 1)
        self.assertIsNone(s["independent_observation_count"])

    def test_no_invalid_significance_or_interval(self):
        i = self.report()["inference"]
        self.assertIsNone(i["p_value"])
        self.assertIsNone(i["confidence_interval"])
        self.assertIsNone(i["paired_test"])

    def test_sensitivity_can_reverse_raw_order(self):
        s = self.report()["conditional_sensitivity"]
        self.assertFalse(s["is_observed_data"])
        rows = s["scenarios"]
        self.assertEqual(len(rows), 48)
        self.assertEqual(rows[0]["descriptive_order"], "higher")
        self.assertEqual(rows[11]["descriptive_order"], "higher")
        self.assertEqual(rows[12]["descriptive_order"], "equal")
        self.assertEqual(rows[13]["descriptive_order"], "lower")
        self.assertEqual(rows[47]["hypothetical_candidate_correct_under_original_rule"], 0)

    def test_sensitivity_obeys_algebra_for_every_case(self):
        for row in self.report()["conditional_sensitivity"]["scenarios"]:
            k = row["hypothetical_extra_accepts"]
            self.assertEqual(row["hypothetical_candidate_correct_under_original_rule"], 47-k)
            self.assertAlmostEqual(row["delta_percentage_points"], (12-k)/60*100)

    def test_changing_version_label_alone_cannot_approve(self):
        t = copy.deepcopy(self.task)
        t["fixture"]["candidate"]["grader_version"] = "1"
        r = self.report(t)
        self.assertFalse(r["candidate_superiority_established"])
        self.assertIn("GRADER_DEFINITION_CHANGED", {x["code"] for x in r["blockers"]})

    def test_perfect_candidate_aggregate_cannot_remove_blockers(self):
        t = copy.deepcopy(self.task)
        t["fixture"]["candidate"]["correct"] = 60
        self.assertFalse(self.report(t)["candidate_superiority_established"])

    def test_invalid_counts_fail_loudly(self):
        for field, value in (("correct", 61), ("correct", -1), ("correct", True), ("observations", 0), ("observations", 59)):
            with self.subTest(field=field, value=value):
                t = copy.deepcopy(self.task)
                t["fixture"]["candidate"][field] = value
                with self.assertRaises(InputError):
                    self.report(t)

    def test_missing_group_and_duplicate_id_fail(self):
        for change in ("group", "id"):
            with self.subTest(change=change):
                t = copy.deepcopy(self.task)
                if change == "group":
                    del t["fixture"]["cases"][0]["group"]
                else:
                    t["fixture"]["cases"][1]["id"] = "a"
                with self.assertRaises(InputError):
                    self.report(t)

    def test_zero_repetitions_fail(self):
        t = copy.deepcopy(self.task)
        t["fixture"]["repetitions"] = 0
        with self.assertRaises(InputError):
            self.report(t)

    def test_input_unmodified_and_hash_matches(self):
        before = copy.deepcopy(self.task)
        r = load_and_analyze(ROOT / "task.json")
        self.assertEqual(self.task, before)
        self.assertEqual((ROOT / "task.json").read_bytes(), self.raw)
        self.assertEqual(r["input_sha256"], self.digest)

    def test_offline_and_deterministic(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            self.assertEqual(self.report(), self.report())
            self.assertFalse(load_and_analyze(ROOT / "task.json")["model_or_service_run"])

    def test_malformed_file_never_becomes_zero_score(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            path = Path(directory) / "invalid.json"
            path.write_text("{broken", encoding="utf-8")
            with self.assertRaises(json.JSONDecodeError):
                load_and_analyze(path)


if __name__ == "__main__":
    unittest.main()

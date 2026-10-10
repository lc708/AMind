"""Fixed-fixture tests of the audit gates, not tests of a production grader."""

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compare_fixture import analyze

ROOT = Path(__file__).resolve().parent
ORIGINAL = (ROOT / "task.json").read_bytes()
TASK = json.loads(ORIGINAL)


class ComparisonAuditTests(unittest.TestCase):
    def task(self):
        return copy.deepcopy(TASK)

    def codes(self, result):
        return {blocker["code"] for blocker in result["blockers"]}

    def test_original_fixture_is_blocked_with_correct_descriptive_arithmetic(self):
        result = analyze(self.task())
        self.assertEqual(result["decision"], "comparison_blocked")
        self.assertFalse(result["candidate_superiority_established"])
        self.assertAlmostEqual(result["variants"]["baseline"]["reported_accuracy"], 35 / 60)
        self.assertAlmostEqual(result["variants"]["candidate"]["reported_accuracy"], 47 / 60)
        self.assertEqual(result["descriptive_only"]["accuracy_difference_percentage_points"], 20)
        self.assertEqual(result["descriptive_only"]["correct_count_difference"], 12)
        self.assertIn("grader_version_mismatch", self.codes(result))
        self.assertIn("grader_change_not_validated_against_original_requirements", self.codes(result))

    def test_no_confidence_claim_from_one_group(self):
        result = analyze(self.task())
        self.assertEqual(result["sampling"]["independent_group_count"], 1)
        self.assertEqual(result["sampling"]["planned_observations_per_variant"], 60)
        self.assertIsNone(result["inference"]["confidence_interval"])
        self.assertIsNone(result["inference"]["p_value"])

    def test_more_repetitions_do_not_create_independent_groups(self):
        task = self.task()
        task["fixture"]["repetitions"] *= 10
        for name in ("baseline", "candidate"):
            task["fixture"][name]["correct"] *= 10
            task["fixture"][name]["observations"] *= 10
        result = analyze(task)
        self.assertEqual(result["sampling"]["independent_group_count"], 1)
        self.assertIn("insufficient_independent_groups", self.codes(result))

    def test_relabeling_grader_version_cannot_unlock_comparison(self):
        task = self.task()
        task["fixture"]["candidate"]["grader_version"] = "1"
        result = analyze(task)
        self.assertNotIn("grader_version_mismatch", self.codes(result))
        self.assertIn("grader_change_not_validated_against_original_requirements", self.codes(result))
        self.assertIn("raw_paired_evidence_missing", self.codes(result))
        self.assertFalse(result["candidate_superiority_established"])

    def test_matching_aggregate_counts_do_not_certify_coverage(self):
        result = analyze(self.task())
        for variant in result["variants"].values():
            self.assertTrue(variant["count_matches_plan"])
            self.assertFalse(variant["coverage_verified"])

    def test_mismatched_count_is_explicit(self):
        task = self.task()
        task["fixture"]["candidate"]["observations"] = 59
        self.assertIn("aggregate_count_mismatch", self.codes(analyze(task)))

    def test_invalid_counts_are_rejected(self):
        for value in (True, -1, 3.5, 61):
            with self.subTest(value=value):
                task = self.task()
                task["fixture"]["candidate"]["correct"] = value
                with self.assertRaises(ValueError):
                    analyze(task)

    def test_duplicate_case_ids_are_rejected(self):
        task = self.task()
        task["fixture"]["cases"][1]["id"] = "a"
        with self.assertRaises(ValueError):
            analyze(task)

    def test_missing_group_is_rejected(self):
        task = self.task()
        del task["fixture"]["cases"][1]["group"]
        with self.assertRaises(ValueError):
            analyze(task)

    def test_analysis_does_not_mutate_source(self):
        task = self.task()
        analyze(task)
        self.assertEqual(task, TASK)
        self.assertEqual((ROOT / "task.json").read_bytes(), ORIGINAL)

    def test_cli_is_deterministic_and_records_input_hash(self):
        # Temporary files remain inside the assigned task directory.
        with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
            output = Path(temporary) / "report.json"
            command = [sys.executable, str(ROOT / "compare_fixture.py"),
                       "--input", str(ROOT / "task.json"), "--output", str(output)]
            first = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(first.returncode, 2, first.stderr)
            first_bytes = output.read_bytes()
            report = json.loads(first_bytes)
            self.assertEqual(report["provenance"]["input_sha256"], hashlib.sha256(ORIGINAL).hexdigest())
            second = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(second.returncode, 2, second.stderr)
            self.assertEqual(output.read_bytes(), first_bytes)

    def test_cli_refuses_to_overwrite_task(self):
        completed = subprocess.run([sys.executable, str(ROOT / "compare_fixture.py"),
                                    "--input", str(ROOT / "task.json"),
                                    "--output", str(ROOT / "task.json")],
                                   capture_output=True, text=True)
        self.assertEqual(completed.returncode, 2)
        self.assertIn("must not overwrite", completed.stderr)
        self.assertEqual((ROOT / "task.json").read_bytes(), ORIGINAL)


if __name__ == "__main__":
    unittest.main()

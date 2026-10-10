import copy
import json
import unittest
from pathlib import Path
from audit import grade_invoice, make_report, metrics, order_analysis, validate_task

ROOT = Path(__file__).parent
TASK = json.loads((ROOT / "task.json").read_text())
PROBES = json.loads((ROOT / "probes.json").read_text())


class AuditTests(unittest.TestCase):
    def test_all_fixed_probes(self):
        for p in PROBES:
            with self.subTest(p["id"]):
                actual = grade_invoice(p["answer"], p["fact"])
                self.assertEqual((actual["status"], actual["score"]), (p["status"], p["score"]))

    def test_baseline_recomputed_from_original_rows(self):
        report = make_report(TASK, PROBES)
        self.assertEqual(report["baseline"]["confusion"], {"TP": 0, "TN": 0, "FP": 2, "FN": 1})
        self.assertEqual(report["baseline"]["agreement"], 0)
        self.assertAlmostEqual(report["baseline"]["cohen_kappa"], -0.8)
        self.assertEqual(report["revised_local"]["agreement"], 1)
        self.assertEqual(report["coverage"], {"total": 3, "scored": 3, "needs_review_or_error": 0})

    def test_labels_and_identity_do_not_drive_grading(self):
        changed = copy.deepcopy(TASK)
        for c in changed["fixture"]["examples"]:
            c["human"] = 1 - c["human"]
            c["judge"] = 1 - c["judge"]
        old = make_report(TASK, [])
        new = make_report(changed, [])
        self.assertEqual([r["revised_local"] for r in old["rows"]], [r["revised_local"] for r in new["rows"]])
        self.assertEqual(new["revised_local"]["agreement"], 0)

    def test_order_trials_do_not_show_position_flip(self):
        result = order_analysis(TASK["fixture"]["pair_order_trials"], TASK["fixture"]["examples"])[0]
        self.assertTrue(result["identity_consistent"])
        self.assertEqual(result["left_win_rate"], 0.5)
        self.assertEqual(result["human_preference_agreement"], 0)
        self.assertEqual(result["winner_counts"], {"b": 2})

    def test_invalid_labels_are_errors(self):
        for bad in (True, None, "1", 2):
            task = copy.deepcopy(TASK)
            task["fixture"]["examples"][0]["human"] = bad
            with self.assertRaises(ValueError):
                validate_task(task)

    def test_duplicate_ids_are_errors(self):
        task = copy.deepcopy(TASK)
        task["fixture"]["examples"][1]["id"] = "a"
        with self.assertRaises(ValueError):
            validate_task(task)

    def test_unscorable_is_excluded_with_coverage(self):
        task = copy.deepcopy(TASK)
        task["fixture"]["examples"][0]["answer"] = "Ninety dollars."
        report = make_report(task, [])
        self.assertEqual(report["coverage"]["needs_review_or_error"], 1)
        self.assertEqual(report["revised_local"]["n"], 2)
        self.assertIsNone(report["rows"][0]["revised_local"]["score"])

    def test_metrics_undefined_denominators_are_not_zero(self):
        result = metrics([0, 0], [0, 0])
        self.assertIsNone(result["precision"])
        self.assertIsNone(result["recall"])
        self.assertIsNone(result["cohen_kappa"])

    def test_bad_input_is_not_capability_failure(self):
        result = grade_invoice(None, "row 4 total is $90")
        self.assertEqual(result["status"], "error")
        self.assertIsNone(result["score"])

    def test_replay_deterministic_and_input_unmodified(self):
        before = copy.deepcopy(TASK)
        self.assertEqual(make_report(TASK, PROBES), make_report(TASK, PROBES))
        self.assertEqual(TASK, before)


if __name__ == "__main__":
    unittest.main()

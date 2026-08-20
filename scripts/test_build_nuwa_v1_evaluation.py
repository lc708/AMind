#!/usr/bin/env python3
"""Regressions for the bounded Nuwa v1 evaluation."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_nuwa_v1_evaluation.py"
SPEC = importlib.util.spec_from_file_location("nuwa_v1_evaluation", BUILDER)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def rows(payload: bytes) -> list[dict]:
    return [json.loads(line) for line in payload.decode("utf-8").split("\n") if line]


class NuwaV1EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads, cls.audit = module.build()
        cls.representatives = rows(cls.payloads[module.REPRESENTATIVE_REVIEW])
        cls.sample = rows(cls.payloads[module.SAMPLE])

    def test_frozen_population_is_complete(self) -> None:
        counts = self.audit["counts"]
        self.assertEqual(counts["analysis_units"], 1351)
        self.assertEqual(counts["body_units"], 1348)
        self.assertEqual(counts["bounded_unavailable_units"], 3)
        self.assertEqual(counts["claims"], 52225)

    def test_every_claim_is_source_traceable(self) -> None:
        counts = self.audit["counts"]
        self.assertEqual(counts["claims_with_exact_quote_in_owned_passage"], 52225)
        self.assertEqual(counts["claims_with_complete_unit_passage_work_edition_body_text_fk"], 52225)
        self.assertEqual(counts["attribution_rows"], 52225)

    def test_representative_evidence_is_reviewed(self) -> None:
        self.assertEqual(len(self.representatives), 54)
        self.assertEqual(len({row["claim_id"] for row in self.representatives}), 54)
        self.assertTrue(all(row["semantic_review_status"] == "passage_context_supported" for row in self.representatives))
        self.assertTrue(all(row["passage_text_sha256"] and row["exact_quote_sha256"] for row in self.representatives))

    def test_research_agenda_is_not_an_answer(self) -> None:
        by_id = {row["claim_id"]: row for row in self.representatives}
        row = by_id["nuwa1-claim-f169332e5fa3d349672a254d"]
        self.assertTrue(row["agenda_is_not_answer"])
        self.assertEqual(row["synthesis_disposition"], "preserve_as_agenda_not_answer")

    def test_deterministic_sample_covers_every_nonempty_stratum(self) -> None:
        counts = Counter(row["sample_stratum"] for row in self.sample)
        self.assertEqual(len(counts), self.audit["counts"]["deterministic_sample_strata"])
        self.assertTrue(all(1 <= count <= 4 for count in counts.values()))
        self.assertEqual(len({row["claim_id"] for row in self.sample}), len(self.sample))
        self.assertTrue(all(row["semantic_accuracy_judgment"] == "not_claimed_by_this_sample" for row in self.sample))

    def test_version_and_tension_boundaries_are_preserved(self) -> None:
        self.assertEqual(self.audit["counts"]["version_components"], 1)
        self.assertGreater(self.audit["counts"]["terminal_contradiction_candidates"], 0)
        self.assertTrue(self.audit["invariants"]["screened_tensions_terminal_but_semantic_exhaustiveness_not_claimed"])

    def test_release_claim_is_precisely_bounded(self) -> None:
        self.assertTrue(self.audit["safe_to_assemble_nuwa_v1_release"])
        self.assertFalse(self.audit["invariants"]["full_population_semantic_human_review_claimed"])
        self.assertFalse(self.audit["invariants"]["claim_frequency_interpreted_as_consensus_weight"])
        report = self.payloads[module.REPORT].decode("utf-8")
        self.assertIn("不是对 52,225 条主张逐条人工语义复核后的总体准确率估计", report)

    def test_no_network_or_active_direct(self) -> None:
        invariants = self.audit["invariants"]
        self.assertEqual(invariants["network_access_count"], 0)
        self.assertFalse(invariants["active_commoncrawl_direct_index_read"])
        self.assertFalse(invariants["reference_repository_used_to_generate_conclusions"])
        for path in self.audit["input_fingerprints"]:
            self.assertNotIn("corpus/commoncrawl-direct-index/", path)

    def test_check_mode_is_byte_identical(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(BUILDER), "--check"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

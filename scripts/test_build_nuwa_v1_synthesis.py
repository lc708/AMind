#!/usr/bin/env python3
"""Regressions for the first Nuwa v1 synthesis."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_nuwa_v1_synthesis.py"
SPEC = importlib.util.spec_from_file_location("nuwa_v1_synthesis", BUILDER)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def rows(payload: bytes) -> list[dict]:
    return [json.loads(line) for line in payload.decode("utf-8").split("\n") if line]


class NuwaV1SynthesisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads, cls.audit = module.build()
        cls.themes = rows(cls.payloads[module.THEMES])
        cls.membership = rows(cls.payloads[module.MEMBERSHIP])
        cls.evidence = rows(cls.payloads[module.EVIDENCE])
        cls.voices = rows(cls.payloads[module.VOICE_PROFILES])
        cls.tensions = rows(cls.payloads[module.SYNTHESIS_TENSIONS])

    def test_frozen_population_and_theme_membership(self) -> None:
        self.assertEqual(self.audit["counts"]["analysis_units"], 1351)
        self.assertEqual(self.audit["counts"]["claims"], 52225)
        self.assertEqual(len(self.membership), 52225)
        self.assertEqual(len({row["claim_id"] for row in self.membership}), 52225)

    def test_themes_are_nonexclusive_and_post_extraction(self) -> None:
        self.assertEqual(len(self.themes), 9)
        self.assertTrue(any(len(row["theme_ids"]) > 1 for row in self.membership))
        self.assertTrue(self.audit["invariants"]["themes_defined_after_atomic_extraction_and_claim_audit"])

    def test_representatives_are_unique_and_source_bound(self) -> None:
        claim_ids = [row["claim_id"] for row in self.evidence]
        self.assertEqual(len(claim_ids), 54)
        self.assertEqual(len(claim_ids), len(set(claim_ids)))
        self.assertTrue(all(row["exact_quote_sha256"] and row["passage_id"] and row["work_id"] for row in self.evidence))
        by_theme = {}
        for row in self.evidence:
            by_theme.setdefault(row["theme_id"], set()).add(row["work_id"])
        self.assertTrue(all(len(works) >= 4 for works in by_theme.values()))
        by_id = {row["claim_id"]: row for row in self.evidence}
        model_welfare = by_id["nuwa1-claim-f169332e5fa3d349672a254d"]
        self.assertEqual(model_welfare["attribution_class"], "research_question_or_agenda")
        self.assertEqual(model_welfare["synthesis_disposition"], "preserve_as_agenda_not_answer")

    def test_voice_profiles_do_not_turn_volume_into_consensus(self) -> None:
        self.assertEqual({row["name"] for row in self.voices}, {"Dario Amodei", "Jack Clark", "Chris Olah", "Amanda Askell", "Anthropic"})
        self.assertTrue(all(row["frequency_interpretation"] == "corpus_presence_not_personal_influence_or_consensus_weight" for row in self.voices))

    def test_tensions_are_preserved(self) -> None:
        self.assertEqual(len(self.tensions), 5)
        self.assertTrue(all(row["terminal_treatment"] == "preserve_both_conditions_no_forced_resolution" for row in self.tensions))

    def test_report_contains_core_boundaries(self) -> None:
        report = self.payloads[module.REPORT].decode("utf-8")
        for phrase in ("篇幅与主张数量只表示语料覆盖", "机构口径不自动等同于任何个人观点", "受控模拟", "唯一明示版本组件"):
            self.assertIn(phrase, report)

    def test_no_network_or_active_direct(self) -> None:
        invariants = self.audit["invariants"]
        self.assertEqual(invariants["network_access_count"], 0)
        self.assertFalse(invariants["active_commoncrawl_direct_index_read"])
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

#!/usr/bin/env python3
"""Regressions for the Nuwa v1 source-bound claim audit."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_nuwa_v1_claim_audit.py"
SPEC = importlib.util.spec_from_file_location("nuwa_v1_claim_audit", BUILDER)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def rows(payload: bytes) -> list[dict]:
    return [json.loads(line) for line in payload.decode("utf-8").split("\n") if line]


class NuwaV1ClaimAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads, cls.audit = module.build()
        cls.attribution = rows(cls.payloads[module.ATTRIBUTION])
        cls.equivalence = rows(cls.payloads[module.EQUIVALENCE])
        cls.versions = rows(cls.payloads[module.VERSIONS])
        cls.tensions = rows(cls.payloads[module.CONTRADICTIONS])

    def test_every_claim_is_attributed_exactly_once(self) -> None:
        self.assertEqual(len(self.attribution), 52225)
        self.assertEqual(len({row["claim_id"] for row in self.attribution}), 52225)

    def test_quoted_and_unknown_voices_are_not_promoted(self) -> None:
        by_id = {row["claim_id"]: row for row in self.attribution}
        claims = module.read_jsonl(module.CLAIMS)
        for claim in claims:
            if claim["epistemic_force"] == "quoted_position" or claim["voice"]["voice_type"] in {"third_party_quote", "unknown"}:
                row = by_id[claim["claim_id"]]
                self.assertIn(
                    row["attribution_class"],
                    {"reported_or_quoted_position", "embedded_artifact_or_verbatim_example"},
                )
                self.assertFalse(row["personal_view_attribution_permitted"])

    def test_document_editorial_is_never_personal(self) -> None:
        for row in self.attribution:
            if row["voice_type"] == "document_editorial":
                self.assertTrue(row["document_editorial_is_not_personal_view"])
                self.assertFalse(row["personal_view_attribution_permitted"])

    def test_explicit_research_agenda_is_not_promoted_to_an_answer(self) -> None:
        by_id = {row["claim_id"]: row for row in self.attribution}
        model_welfare = by_id["nuwa1-claim-f169332e5fa3d349672a254d"]
        self.assertEqual(model_welfare["attribution_class"], "research_question_or_agenda")
        self.assertEqual(model_welfare["synthesis_disposition"], "preserve_as_agenda_not_answer")

    def test_equivalence_components_are_disjoint(self) -> None:
        members = [claim_id for row in self.equivalence for claim_id in row["member_claim_ids"]]
        self.assertEqual(len(members), len(set(members)))
        self.assertTrue(all(row["member_count"] == len(row["member_claim_ids"]) >= 2 for row in self.equivalence))

    def test_version_boundary_is_preserved(self) -> None:
        self.assertEqual(len(self.versions), 1)
        row = self.versions[0]
        self.assertEqual(row["direction"], "unknown_preserve_both")
        self.assertEqual(len(row["unit_ids"]), 2)
        self.assertEqual(len(row["body_sha256s"]), 2)
        self.assertEqual(row["terminal_disposition"], "preserve_distinct_versions_no_supersession_inference")

    def test_conditioned_emotion_results_are_not_a_contradiction(self) -> None:
        pair = {
            "nuwa1-claim-84ddb4fcbbdba032e0d5f83c",
            "nuwa1-claim-fd6d625ec0cafb37e88d2797",
        }
        matching = [row for row in self.tensions if set(row["claim_ids"]) == pair]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["terminal_disposition"], "conditioned_experiment_contrast_not_contradiction")

    def test_all_screened_tensions_are_terminal_but_not_claimed_exhaustive(self) -> None:
        self.assertTrue(self.tensions)
        self.assertTrue(all(not row["unresolved"] for row in self.tensions))
        self.assertFalse(self.audit["semantic_contradiction_exhaustiveness_claimed"])
        self.assertTrue(self.audit["safe_to_begin_worldview_synthesis"])

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

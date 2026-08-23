#!/usr/bin/env python3
"""Regressions for the deterministic AMind v1 public release package."""

from __future__ import annotations

import gzip
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "scripts/build_amind_v1_release.py"
SPEC = importlib.util.spec_from_file_location("amind_v1_release", BUILDER)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class AMindV1ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payloads, cls.audit = module.build()
        cls.manifest = json.loads(cls.payloads[module.MANIFEST])

    def test_release_population_is_frozen(self) -> None:
        counts = self.manifest["counts"]
        self.assertEqual(counts["analysis_units"], 1351)
        self.assertEqual(counts["body_units"], 1348)
        self.assertEqual(counts["bounded_unavailable_units"], 3)
        self.assertEqual(counts["passages"], 13436)
        self.assertEqual(counts["claims"], 52225)
        self.assertEqual(counts["published_artifacts"], 21)

    def test_every_artifact_is_hash_bound(self) -> None:
        self.assertEqual(len(self.manifest["artifacts"]), 21)
        for row in self.manifest["artifacts"]:
            payload = self.payloads[ROOT / row["published_file"]]
            self.assertEqual(module.sha256_bytes(payload), row["published_sha256"])
            source = (ROOT / row["source_file"]).read_bytes()
            self.assertEqual(module.sha256_bytes(source), row["source_sha256"])

    def test_gzip_artifacts_replay_exact_source_bytes(self) -> None:
        compressed = [row for row in self.manifest["artifacts"] if row["compression"] == "gzip"]
        self.assertEqual(len(compressed), 5)
        for row in compressed:
            payload = self.payloads[ROOT / row["published_file"]]
            self.assertEqual(gzip.decompress(payload), (ROOT / row["source_file"]).read_bytes())

    def test_no_oversized_github_artifact(self) -> None:
        for path, payload in self.payloads.items():
            self.assertLess(len(payload), 100 * 1024 * 1024, path)

    def test_release_discloses_semantic_boundary(self) -> None:
        boundary = self.manifest["publication_boundary"]
        self.assertFalse(boundary["full_population_semantic_human_review_claimed"])
        self.assertFalse(boundary["raw_capture_blobs_included"])
        readme = self.payloads[module.RELEASE_README].decode("utf-8")
        self.assertIn("不声称 52,225 条主张全部经过逐条人工语义复核", readme)

    def test_public_brand_and_usage_are_unambiguous(self) -> None:
        self.assertEqual(self.manifest["release_id"], "amind-v1")
        self.assertEqual(self.manifest["release_name"], "AMind v1")
        self.assertEqual(self.manifest["schema_name"], "amind-v1-release-manifest")
        readme = self.payloads[module.RELEASE_README].decode("utf-8")
        self.assertIn("不是模型、应用或 Codex 技能", readme)
        self.assertIn("不需要安装第三方依赖", readme)
        self.assertIn("python3 -B amind.py search", readme)
        self.assertNotIn("Nuwa v1", readme)
        compatibility = self.manifest["compatibility"]
        self.assertIn("nuwa1-", compatibility["legacy_internal_identifier_prefixes"])

    def test_release_contains_dependency_free_browser(self) -> None:
        browser = ROOT / "release/amind-v1/amind.py"
        source = ROOT / "scripts/amind_v1.py"
        self.assertEqual(self.payloads[browser], source.read_bytes())

    def test_release_gate_is_pass_and_offline(self) -> None:
        self.assertEqual(self.audit["verdict"], "PASS")
        self.assertTrue(self.audit["safe_to_publish_release_package"])
        self.assertEqual(self.audit["invariants"]["network_access_count"], 0)
        self.assertFalse(self.audit["invariants"]["active_commoncrawl_direct_index_read"])
        self.assertFalse(self.audit["invariants"]["installation_required"])
        self.assertFalse(self.audit["invariants"]["codex_skill_required"])

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

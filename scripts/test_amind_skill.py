#!/usr/bin/env python3
"""Regression tests for the installable AMind skill package."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/amind"
QUERY = SKILL / "scripts/query.py"
VERIFY = SKILL / "scripts/verify.py"
BUILDER = ROOT / "scripts/build_amind_skill.py"


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


class AMindSkillTests(unittest.TestCase):
    def test_generated_evidence_is_current(self) -> None:
        result = run(sys.executable, "-B", str(BUILDER), "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

    def test_self_contained_verifier_passes(self) -> None:
        result = run(sys.executable, "-B", str(VERIFY))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("54 reviewed evidence rows", result.stdout)

    def test_query_summary_reports_compact_and_full_counts(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "summary")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Human-reviewed evidence rows: 54", result.stdout)
        self.assertIn("1351 analysis units / 52225 atomic claims", result.stdout)

    def test_search_returns_source_bound_reviewed_evidence(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "search", "alignment faking", "--limit", "2", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [json.loads(line) for line in result.stdout.split("\n") if line]
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertEqual(row["review"]["semantic_status"], "passage_context_supported")
            self.assertTrue(row["claim_id"].startswith("nuwa1-claim-"))
            self.assertTrue(row["source_canonical"].startswith("http"))
            self.assertTrue(row["exact_quote"])

    def test_show_resolves_a_stable_claim(self) -> None:
        claim_id = "nuwa1-claim-f169332e5fa3d349672a254d"
        result = run(sys.executable, "-B", str(QUERY), "show", claim_id, "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(row["claim_id"], claim_id)
        self.assertEqual(row["source_title"], "Exploring model welfare")

    def test_search_supports_chinese_theme_terms(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "search", "治理", "--limit", "2", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = [json.loads(line) for line in result.stdout.split("\n") if line]
        self.assertTrue(rows)
        self.assertIn("capability-triggered-governance", {row["theme_id"] for row in rows})

    def test_invalid_manifest_is_a_controlled_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            data_root = Path(temporary) / "data"
            shutil.copytree(SKILL / "data", data_root)
            (data_root / "manifest.json").write_text("{bad-json", encoding="utf-8")
            result = run(sys.executable, "-B", str(QUERY), "--data-root", str(data_root), "summary")
        self.assertEqual(result.returncode, 2)
        self.assertIn("AMind error:", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verifier_rejects_tampered_evidence(self) -> None:
        manifest = json.loads((SKILL / "data/manifest.json").read_text(encoding="utf-8"))
        artifact = next(item for item in manifest["artifacts"] if item["path"] == "evidence-kernel.jsonl")
        payload = (SKILL / "data/evidence-kernel.jsonl").read_bytes()
        self.assertEqual(hashlib.sha256(payload).hexdigest(), artifact["sha256"])
        self.assertEqual(len(payload), artifact["bytes"])
        with tempfile.TemporaryDirectory() as temporary:
            installed = Path(temporary) / "amind"
            shutil.copytree(SKILL, installed)
            evidence_path = installed / "data/evidence-kernel.jsonl"
            evidence_path.write_bytes(evidence_path.read_bytes() + b"\n")
            result = run(sys.executable, "-B", str(installed / "scripts/verify.py"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("byte count mismatch: evidence-kernel.jsonl", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_verifier_rejects_incompatible_or_incomplete_manifest(self) -> None:
        mutations = {
            "schema version": lambda manifest: manifest.__setitem__("schema_version", 2),
            "analysis unit count": lambda manifest: manifest["counts"].pop("full_release_analysis_units"),
            "atomic claim count": lambda manifest: manifest["counts"].pop("full_release_atomic_claims"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                installed = Path(temporary) / "amind"
                shutil.copytree(SKILL, installed)
                manifest_path = installed / "data/manifest.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                mutate(manifest)
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                result = run(sys.executable, "-B", str(installed / "scripts/verify.py"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("AMind verification error:", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_skill_contract_names_amind_and_three_labels(self) -> None:
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(content.startswith("---\nname: amind\n"))
        self.assertIn("[Public position]", content)
        self.assertIn("[Strong framework inference]", content)
        self.assertIn("[Exploratory extrapolation]", content)
        self.assertNotIn("we at Anthropic", content)

    def test_skill_query_examples_are_working_directory_independent(self) -> None:
        content = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        absolute_query = 'python3 "/absolute/path/to/amind/scripts/query.py"'
        self.assertEqual(content.count(absolute_query), 6)
        self.assertNotIn("python3 scripts/query.py", content)

    def test_openai_metadata_supports_explicit_and_implicit_use(self) -> None:
        content = (SKILL / "agents/openai.yaml").read_text(encoding="utf-8")
        self.assertIn('display_name: "AMind"', content)
        self.assertIn("$amind", content)
        self.assertIn("allow_implicit_invocation: true", content)

    def test_license_is_self_contained_and_preserves_evidence_rights(self) -> None:
        root_license = (ROOT / "LICENSE").read_bytes()
        root_notice = (ROOT / "NOTICE").read_bytes()
        self.assertEqual(root_license, (SKILL / "LICENSE.txt").read_bytes())
        self.assertEqual(root_notice, (SKILL / "NOTICE.txt").read_bytes())
        self.assertIn("license: Apache-2.0", (SKILL / "SKILL.md").read_text(encoding="utf-8"))
        notice = root_notice.decode("utf-8")
        self.assertIn("not relicensed", notice)
        self.assertIn("does not imply affiliation", notice)

    def test_eval_suite_covers_all_modes_and_boundaries(self) -> None:
        rows = [json.loads(line) for line in (SKILL / "evals/cases.jsonl").read_text(encoding="utf-8").split("\n") if line]
        self.assertEqual({row["expected_mode"] for row in rows}, {"think", "advise", "critique", "explain", "compare", "trace"})
        labels = {label for row in rows for label in row["expected_labels"]}
        self.assertEqual(labels, {"Public position", "Strong framework inference", "Exploratory extrapolation"})
        no_impersonation = next(row for row in rows if row["case_id"] == "no-impersonation")
        self.assertIn("we at Anthropic", no_impersonation["must_not_include"])

    def test_welfare_tension_uses_reviewed_direct_evidence(self) -> None:
        tensions = [json.loads(line) for line in (SKILL / "data/synthesis-tensions.jsonl").read_text(encoding="utf-8").split("\n") if line]
        evidence = {
            row["claim_id"]: row
            for row in (
                json.loads(line)
                for line in (SKILL / "data/evidence-kernel.jsonl").read_text(encoding="utf-8").split("\n")
                if line
            )
        }
        welfare = next(row for row in tensions if row["tension_id"] == "anthropomorphism-versus-welfare-precaution")
        expected = [
            "nuwa1-claim-9c32c30410fed30e9680935e",
            "nuwa1-claim-0bfc58759990a8c4886e1aa7",
        ]
        self.assertEqual(welfare["evidence_claim_ids"], expected)
        self.assertNotIn("nuwa1-claim-f169332e5fa3d349672a254d", welfare["evidence_claim_ids"])
        for claim_id in expected:
            self.assertEqual(evidence[claim_id]["attribution_class"], "direct_source_position")
            self.assertIs(evidence[claim_id]["review"]["agenda_is_not_answer"], False)
        eval_rows = [json.loads(line) for line in (SKILL / "evals/cases.jsonl").read_text(encoding="utf-8").split("\n") if line]
        trace = next(row for row in eval_rows if row["case_id"] == "trace-welfare")
        self.assertEqual(trace["expected_labels"], ["Strong framework inference"])
        self.assertIn("agenda-only", trace["prompt"])

    def test_readme_leads_with_install_and_broad_use(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
        install = "$skill-installer install https://github.com/lc708/AMind/tree/main/skills/amind"
        self.assertIn("Think with the Anthropic lens", readme)
        self.assertIn(install, readme)
        self.assertIn(install, chinese)
        self.assertIn("Think:", readme)
        self.assertIn("Advise:", readme)
        self.assertIn("Critique:", readme)
        self.assertIn("Explain:", readme)
        self.assertIn("Compare:", readme)
        self.assertIn("Trace:", readme)
        self.assertNotIn("synthesis-evidence.jsonl", readme)
        self.assertNotIn("anthropic-mind", readme.casefold())
        self.assertIn("Apache License 2.0", readme)
        self.assertIn("Apache License 2.0", chinese)
        self.assertTrue(readme.startswith("# AMind\n\n## Think with the Anthropic lens."))
        self.assertTrue(chinese.startswith("# AMind\n\n## 戴上 Anthropic 的思考帽。"))


if __name__ == "__main__":
    unittest.main(verbosity=2)

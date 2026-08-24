#!/usr/bin/env python3
"""Regression tests for the installable AMind skill package."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/amind"
QUERY = SKILL / "scripts/query.py"
VERIFY = SKILL / "scripts/verify.py"
BUILDER = ROOT / "scripts/build_amind_skill.py"
INDEX_BUILDER = ROOT / "scripts/build_amind_skill_index.py"
INDEX_BUILDER_SPEC = importlib.util.spec_from_file_location("build_amind_skill_index", INDEX_BUILDER)
assert INDEX_BUILDER_SPEC and INDEX_BUILDER_SPEC.loader
INDEX_BUILDER_MODULE = importlib.util.module_from_spec(INDEX_BUILDER_SPEC)
INDEX_BUILDER_SPEC.loader.exec_module(INDEX_BUILDER_MODULE)


def run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(args),
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def json_lines(payload: str) -> list[dict]:
    return [json.loads(line) for line in payload.splitlines() if line]


class AMindSkillTests(unittest.TestCase):
    def test_generated_evidence_is_current(self) -> None:
        result = run(sys.executable, "-B", str(BUILDER), "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS", result.stdout)

        index_result = run(sys.executable, "-B", str(INDEX_BUILDER), "--check")
        self.assertEqual(index_result.returncode, 0, index_result.stdout + index_result.stderr)
        self.assertIn("52,225 claims", index_result.stdout)

    def test_index_builder_rejects_duplicate_passage_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "passages.jsonl"
            path.write_text('{"passage_id":"passage-1"}\n{"passage_id":"passage-1"}\n', encoding="utf-8")
            with self.assertRaisesRegex(INDEX_BUILDER_MODULE.IndexBuildError, "duplicate passage ID: passage-1"):
                INDEX_BUILDER_MODULE.validated_passage_ids(path)

    def test_index_builder_rejects_missing_or_unknown_claim_passage_ids(self) -> None:
        passage_ids = {"passage-1"}
        cases = (
            ({}, "missing claim passage ID: claim-1"),
            ({"passage_id": "passage-2"}, "unknown claim passage: claim-1/passage-2"),
        )
        for evidence, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(INDEX_BUILDER_MODULE.IndexBuildError, message):
                INDEX_BUILDER_MODULE.validated_claim_passage_id("claim-1", evidence, passage_ids)

    def test_self_contained_verifier_passes(self) -> None:
        result = run(sys.executable, "-B", str(VERIFY))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("52,225 indexed claims", result.stdout)
        self.assertIn("54 reviewed gold rows", result.stdout)

    def test_query_summary_reports_compact_and_full_counts(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "summary")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Searchable atomic claims: 52225", result.stdout)
        self.assertIn("Indexed analysis units: 1351", result.stdout)
        self.assertIn("Bundled passage contexts: 13436", result.stdout)
        self.assertIn("Human-reviewed gold rows: 54", result.stdout)

    def test_search_returns_source_bound_full_index_evidence(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "search", "alignment faking", "--limit", "2", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = json_lines(result.stdout)
        self.assertGreaterEqual(len(rows), 1)
        for row in rows:
            self.assertIn(row["evidence_tier"], {"gold_human_reviewed", "full_release_machine_checked"})
            self.assertIn(
                row["review"]["semantic_status"],
                {"passage_context_supported", "machine_checked_not_human_reviewed"},
            )
            self.assertEqual(row["synthesis_disposition"], "eligible_for_source_level_synthesis")
            self.assertEqual(row["retrieval"]["relevance_tier"], "strong")
            self.assertEqual(set(row["retrieval"]["matched_query_terms"]), {"alignment", "faking"})
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

    def test_show_returns_bound_passage_context(self) -> None:
        claim_id = "nuwa1-claim-f169332e5fa3d349672a254d"
        result = run(sys.executable, "-B", str(QUERY), "show", claim_id, "--passage", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(row["evidence_tier"], "gold_human_reviewed")
        self.assertGreater(len(row["passage"]["text"]), 1000)
        self.assertIn(row["exact_quote"], row["passage"]["text"])
        self.assertEqual(len(row["passage"]["text_sha256"]), 64)

    def test_search_supports_chinese_theme_terms(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "search", "治理", "--limit", "2", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = json_lines(result.stdout)
        self.assertTrue(rows)
        self.assertTrue(all("capability-triggered-governance" in row["theme_ids"] for row in rows))
        self.assertTrue(all(row["retrieval"]["relevance_tier"] == "theme_routed" for row in rows))

    def test_attribution_filter_precedes_equivalence_collapse(self) -> None:
        result = run(
            sys.executable,
            "-B",
            str(QUERY),
            "search",
            "seven hour autonomous Rakuten refactoring",
            "--limit",
            "3",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        rows = json_lines(result.stdout)
        claim = next(row for row in rows if row["claim_id"] == "nuwa1-claim-fac7615b8bec3d3241603dcd")
        self.assertEqual(claim["synthesis_disposition"], "eligible_for_source_level_synthesis")
        self.assertEqual(claim["equivalence"]["component_id"], "nuwa1-equivalence-0982c66b7cb5f9f2e2de")
        self.assertEqual(
            claim["equivalence"]["representative_claim_id"],
            "nuwa1-claim-747ac9f8510e0f00e4027327",
        )
        components = [row["equivalence"]["component_id"] for row in rows if row["equivalence"]["component_id"]]
        self.assertEqual(len(components), len(set(components)))

    def test_stats_exposes_corpus_concentration_without_treating_it_as_weight(self) -> None:
        result = run(sys.executable, "-B", str(QUERY), "stats", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        stats = json.loads(result.stdout)
        self.assertEqual(stats["total_claims"], 52225)
        self.assertEqual(stats["total_sources"], 1351)
        self.assertEqual(stats["source_level_direct_claims"], 45941)
        self.assertEqual(stats["equivalence_extra_rows"], 217)
        jack = next(row for row in stats["voices"] if row["name"] == "Jack Clark")
        self.assertEqual(
            jack,
            {
                "agenda_claims": 1,
                "claims": 10835,
                "direct_claims": 7532,
                "name": "Jack Clark",
                "reported_claims": 3302,
                "sources": 480,
            },
        )
        hosts = {row["host"]: row for row in stats["source_hosts"]}
        self.assertEqual(hosts["jack-clark.net"]["claims"], 11168)
        self.assertEqual(hosts["transformer-circuits.pub"]["claims"], 12248)
        self.assertEqual(hosts["transformer-circuits.pub"]["claims_per_source"], 240.16)

    def test_gold_kernel_distribution_explains_old_jack_repetition(self) -> None:
        rows = json_lines((SKILL / "data/evidence-kernel.jsonl").read_text(encoding="utf-8"))
        jack = [row for row in rows if (row.get("voice") or {}).get("name") == "Jack Clark"]
        self.assertEqual(len(jack), 11)
        self.assertEqual(len({row["theme_id"] for row in jack}), 6)
        scaling = [row for row in jack if row["theme_id"] == "capability-scaling-under-uncertainty"]
        self.assertEqual(len(scaling), 3)

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
            "indexed claim count": lambda manifest: manifest["counts"].pop("full_index_atomic_claims"),
            "passage count": lambda manifest: manifest["counts"].pop("full_index_passages"),
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
        self.assertEqual(content.count(absolute_query), 9)
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

    def test_retrieval_eval_suite(self) -> None:
        cases = [
            json.loads(line)
            for line in (SKILL / "evals/retrieval-cases.jsonl").read_text(encoding="utf-8").splitlines()
            if line
        ]
        self.assertEqual(len(cases), 4)
        for case in cases:
            with self.subTest(case_id=case["case_id"]):
                result = run(
                    sys.executable,
                    "-B",
                    str(QUERY),
                    "search",
                    case["query"],
                    *case["arguments"],
                    "--json",
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                rows = json_lines(result.stdout)
                self.assertTrue(rows)
                expected = case["expected"]
                if "top_source_title" in expected:
                    self.assertEqual(rows[0]["source_title"], expected["top_source_title"])
                if "minimum_strong_results" in expected:
                    self.assertGreaterEqual(
                        sum(row["retrieval"]["relevance_tier"] == "strong" for row in rows),
                        expected["minimum_strong_results"],
                    )
                if "required_relevance_tier" in expected:
                    self.assertTrue(
                        all(row["retrieval"]["relevance_tier"] == expected["required_relevance_tier"] for row in rows)
                    )
                if "minimum_unique_works" in expected:
                    self.assertGreaterEqual(len({row["work_id"] for row in rows}), expected["minimum_unique_works"])
                if "maximum_per_voice" in expected:
                    voices = Counter(
                        row["voice"].get("name") or row["voice"].get("organization") or "Unattributed source voice"
                        for row in rows
                    )
                    self.assertLessEqual(max(voices.values()), expected["maximum_per_voice"])
                if "maximum_per_host" in expected:
                    hosts = Counter(row["source_host"] for row in rows)
                    self.assertLessEqual(max(hosts.values()), expected["maximum_per_host"])
                if "required_detected_theme_id" in expected:
                    self.assertTrue(
                        all(
                            expected["required_detected_theme_id"] in row["retrieval"]["detected_theme_ids"]
                            for row in rows
                        )
                    )
                if "required_result_theme_id" in expected:
                    self.assertTrue(
                        all(expected["required_result_theme_id"] in row["theme_ids"] for row in rows)
                    )
                if "excluded_source_titles" in expected:
                    self.assertTrue(set(expected["excluded_source_titles"]).isdisjoint({row["source_title"] for row in rows}))
                if "required_query_terms" in expected:
                    required = set(expected["required_query_terms"])
                    self.assertTrue(
                        all(required.issubset(row["retrieval"]["matched_query_terms"]) for row in rows)
                    )

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

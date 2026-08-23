#!/usr/bin/env python3
"""Tests for the dependency-free AMind v1 browser."""

from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/amind_v1.py"
SPEC = importlib.util.spec_from_file_location("amind_v1", CLI)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)
RELEASE = ROOT / "release/amind-v1"


class AMindV1Tests(unittest.TestCase):
    def test_summary_uses_frozen_counts(self) -> None:
        stream = io.StringIO()
        with redirect_stdout(stream):
            code = module.command_summary(RELEASE, type("Args", (), {})())
        self.assertEqual(code, 0)
        output = stream.getvalue()
        self.assertIn("AMind v1", output)
        self.assertIn("原子主张：52225", output)
        self.assertIn("分析单位：1351", output)

    def test_theme_catalog_has_nine_rows(self) -> None:
        rows = list(module.iter_jsonl(RELEASE / "data/theme-catalog.jsonl"))
        self.assertEqual(len(rows), 9)
        self.assertEqual(len({row["theme_id"] for row in rows}), 9)

    def test_search_finds_source_bound_claim(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "search", "alignment faking", "--limit", "1", "--json"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = json.loads(result.stdout)
        self.assertTrue(row["claim_id"].startswith("nuwa1-claim-"))
        searchable = row["proposition"] + row["exact_quote"] + row["source_title"]
        self.assertIn("alignment faking", searchable.lower())
        self.assertTrue(row["analysis_unit_id"])
        self.assertTrue(row["source_title"])

    def test_show_resolves_stable_compatibility_id(self) -> None:
        claim_id = "nuwa1-claim-f169332e5fa3d349672a254d"
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "show", claim_id, "--json"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        row = json.loads(result.stdout)
        self.assertEqual(row["claim_id"], claim_id)
        self.assertEqual(row["source_title"], "Exploring model welfare")

    def test_missing_claim_returns_one(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(CLI), "show", "missing-claim"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("未找到主张", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

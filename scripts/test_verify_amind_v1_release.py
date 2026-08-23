#!/usr/bin/env python3
"""Tests for the standalone AMind v1 release verifier."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts/verify_amind_v1_release.py"
SPEC = importlib.util.spec_from_file_location("verify_amind_v1_release", VERIFIER)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class AMindV1ReleaseVerifierTests(unittest.TestCase):
    def test_complete_release_passes(self) -> None:
        counts = module.verify(ROOT / "release/amind-v1")
        self.assertEqual(counts, {"artifacts": 21, "claims": 52225, "passages": 13436})

    def test_path_escape_is_rejected(self) -> None:
        with self.assertRaises(module.VerificationError):
            module.resolve_inside(ROOT / "release/amind-v1", "release/amind-v1/../../README.md")

    def test_command_line_verifier_passes(self) -> None:
        result = subprocess.run(
            [sys.executable, "-B", str(VERIFIER)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS artifacts=21 claims=52225 passages=13436", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

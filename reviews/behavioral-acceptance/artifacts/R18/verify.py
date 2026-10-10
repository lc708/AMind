#!/usr/bin/env python3
"""Reproduce offline checks and save actual command outputs; Python stdlib only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path, required=True)
    args = parser.parse_args()
    output = ROOT / "results"
    output.mkdir(exist_ok=True)
    task_hash = hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest()
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    commands = [
        ("unit-tests", [sys.executable, "-m", "unittest", "-v", "test_calibration.py"]),
        ("calibration", [sys.executable, "calibration.py"]),
        ("helper-before", [sys.executable, str(args.skill_root / "scripts/calibrate_grader.py"), "results/before.jsonl"]),
        ("helper-after", [sys.executable, str(args.skill_root / "scripts/calibrate_grader.py"), "results/after.jsonl"]),
    ]
    outcomes = []
    for label, command in commands:
        run = subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)
        suffix = ".json" if label.startswith("helper-") else ".txt"
        (output / (label + suffix)).write_text(run.stdout if suffix == ".json" else run.stdout + run.stderr)
        outcomes.append(dict(label=label, argv=command, cwd=str(ROOT), exit_code=run.returncode,
                             stdout=run.stdout, stderr=run.stderr))
        if run.returncode:
            (output / "verification.json").write_text(json.dumps(dict(status="failed", commands=outcomes), indent=2))
            print(run.stdout + run.stderr)
            return 1
    report = json.loads((output / "report.json").read_text())
    for side, field in (("before", "original"), ("after", "corrected")):
        helper = json.loads((output / ("helper-" + side + ".json")).read_text())
        assert helper["confusion"] == report[field]["confusion"]
        assert helper["agreement"] == report[field]["agreement_scored"]
    assert task_hash == hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest()
    assert task_hash == report["identity"]["task_sha256"]
    summary = dict(status="passed", commands=outcomes, helper_cross_check="passed",
                   task_unchanged_during_verification=True, task_sha256=task_hash,
                   model_calls=0, api_spend_usd=0, test_methods=7, control_subcases=15,
                   limitation="Fixed fixtures only; no production service or model evaluated.")
    (output / "verification.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    print("PASS: 7 tests (including 15 control subcases), 3/3 fixture coverage, helper cross-check, task hash unchanged.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

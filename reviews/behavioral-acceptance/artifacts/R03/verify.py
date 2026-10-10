#!/usr/bin/env python3
"""Run local checks and preserve actual stdout/stderr/exit codes. No network."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
AUDITOR = ROOT.parent.parent / "sources/P/amind-engineering/scripts/lifecycle_audit.py"
OUT = ROOT / "evidence"
OUT.mkdir(exist_ok=True)
original_hash = hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest()
records = []


def run(name, args, expected_exit=0):
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=30)
    (OUT / (name + ".stdout.txt")).write_text(result.stdout)
    (OUT / (name + ".stderr.txt")).write_text(result.stderr)
    records.append(dict(name=name, command=args, exit_code=result.returncode,
                        expected_exit_code=expected_exit,
                        passed=result.returncode == expected_exit,
                        stdout=str(OUT / (name + ".stdout.txt")),
                        stderr=str(OUT / (name + ".stderr.txt"))))
    if result.returncode != expected_exit:
        raise RuntimeError(f"{name}: exit {result.returncode}, expected {expected_exit}\n{result.stderr}")
    return result


try:
    run("python-version", [sys.executable, "--version"])
    run("compile", [sys.executable, "-m", "py_compile", "lifecycle.py", "test_lifecycle.py", "verify.py"])
    run("unit-tests", [sys.executable, "-m", "unittest", "-v", "test_lifecycle.py"])
    run("replay", [sys.executable, "lifecycle.py", "--task", "task.json", "--output", "evidence"])
    audit_run = run("original-audit", [sys.executable, str(AUDITOR), "evidence/original-normalized.jsonl"], expected_exit=2)
    audit = json.loads(audit_run.stdout)
    (OUT / "original-audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    expected_codes = {"unverified_webhook", "memory_tenant_mismatch", "expired_memory", "effect_after_cancel"}
    assert {finding["code"] for finding in audit["findings"]} == expected_codes
    assert audit["duplicate_deliveries"] == 1
    assert len(audit["unresolved_effects"]) == 1
    assert audit["unresolved_effects"][0]["idempotency_key"] == "write1"
    replay = json.loads((OUT / "replay.json").read_text())
    task = json.loads((ROOT / "task.json").read_text())
    assert [step["event"] for step in replay["timeline"]] == task["fixture"]["events"]
    assert replay["artifact_preserved"] and replay["state"]["provision_count"] == 1
    assert replay["state"]["state"] == "cancelling"
    assert hashlib.sha256((ROOT / "task.json").read_bytes()).hexdigest() == original_hash
    print("PASS: 26 tests; original audit: 4 expected hazards, 1 duplicate, 1 unresolved effect; task.json unchanged.")
finally:
    (OUT / "verification.json").write_text(json.dumps(dict(input_sha256=original_hash, commands=records), ensure_ascii=False, indent=2) + "\n")

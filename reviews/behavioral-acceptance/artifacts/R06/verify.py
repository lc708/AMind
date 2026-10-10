"""Run the offline comparison and tests, saving actual commands and outputs."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
before = (ROOT / "task.json").read_bytes()
commands = [
    [sys.executable, "compare.py", "--input", "task.json", "--output", "comparison.json"],
    [sys.executable, "-m", "unittest", "-v", "test_compare.py"],
]
records = []
for command in commands:
    run = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, timeout=30)
    records.append({"argv": command, "cwd": str(ROOT), "exit_code": run.returncode,
                    "stdout": run.stdout, "stderr": run.stderr})
    print("COMMAND:", " ".join(command))
    print(run.stdout + run.stderr, end="")
first = (ROOT / "comparison.json").read_bytes()
run = subprocess.run(commands[0], cwd=ROOT, text=True, capture_output=True, timeout=30)
records.append({"argv": commands[0], "cwd": str(ROOT), "purpose": "deterministic rerun",
                "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
checks = {
    "commands_passed": all(row["exit_code"] == 0 for row in records),
    "task_json_unchanged": before == (ROOT / "task.json").read_bytes(),
    "comparison_byte_identical_on_rerun": first == (ROOT / "comparison.json").read_bytes(),
}
log = {"python": sys.version, "commands": records, "checks": checks,
       "input_sha256": hashlib.sha256(before).hexdigest()}
(ROOT / "verification.json").write_text(json.dumps(log, indent=2) + "\n", encoding="utf-8")
print(json.dumps(checks, indent=2))
raise SystemExit(0 if all(checks.values()) else 1)

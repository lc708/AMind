"""Repeatable offline checks; persist complete command output and exit codes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", type=Path,
                        help="Optional assigned amind-engineering package for structural audit")
    args = parser.parse_args()
    commands = [
        [sys.executable, "-m", "py_compile", "integration.py", "legacy.py", "demo.py", "test_integration.py", "verify.py"],
        [sys.executable, "-m", "unittest", "-v", "test_integration.py"],
        [sys.executable, "demo.py"],
    ]
    if args.skill_root:
        commands.append([sys.executable, str(args.skill_root / "scripts/context_audit.py"),
                         "--trace", str(ROOT / "continuation-trace.jsonl")])
    checks = []
    for command in commands:
        start = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=30)
        checks.append({"command": command, "cwd": str(ROOT), "exit_code": result.returncode,
                       "stdout": result.stdout, "stderr": result.stderr,
                       "elapsed_seconds": round(time.monotonic() - start, 6)})
        if result.returncode:
            break
    report = {"evidence": "local fixed fixtures; no live service or model behavior measured",
              "python_version": sys.version, "checks": checks,
              "passed": len(checks) == len(commands) and all(x["exit_code"] == 0 for x in checks)}
    (ROOT / "verification.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for check in checks:
        if "context_audit.py" in " ".join(check["command"]):
            (ROOT / "context-audit.json").write_text(check["stdout"])
    print(json.dumps({"passed": report["passed"], "checks": len(checks),
                      "evidence": str(ROOT / "verification.json")}))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

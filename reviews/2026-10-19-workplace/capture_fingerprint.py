#!/usr/bin/env python3
"""Freeze completed captured deliveries before grading, or check their bytes."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def inventory(plan):
    files = {}
    for run in plan["runs"]:
        root = OUT / "runs" / run["run_id"]
        if not (root / "capture.json").is_file():
            raise RuntimeError("Phase incomplete: " + run["run_id"])
        for path in root.rglob("*"):
            if path.is_symlink():
                raise ValueError("Unexpected symlink in captured artifacts: " + str(path))
            if path.is_file():
                files[str(path.relative_to(OUT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="main-plan.json")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    plan = json.loads((OUT / args.plan).read_text())
    path = OUT / (Path(args.plan).stem + "-captured-files.json")
    files = inventory(plan)
    if args.verify:
        previous = json.loads(path.read_text())
        assert previous["files_sha256"] == files, "Captured artifacts changed after fingerprint"
    else:
        assert not path.exists(), "Refusing to replace frozen capture fingerprints"
        path.write_text(json.dumps({"at_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                                    "plan": args.plan, "runs": len(plan["runs"]), "files_sha256": files}, indent=2) + "\n")
    print(json.dumps({"mode": "verify" if args.verify else "freeze", "runs": len(plan["runs"]), "files": len(files), "success": True}))


if __name__ == "__main__":
    main()

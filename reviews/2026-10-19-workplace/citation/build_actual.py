#!/usr/bin/env python3
"""Collect deliverables without printing answers; call the frozen blind binder."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent
STUDY = OUT.parent


def main():
    plan = json.loads((STUDY / "main-plan.json").read_text())
    missing = [r["run_id"] for r in plan["runs"] if not (STUDY / "runs" / r["run_id"] / "capture.json").exists()]
    if missing:
        raise RuntimeError("Full main phase required before any answer inspection: " + ",".join(missing))
    rows, selection = [], []
    path = OUT / "actual-inputs.private.jsonl"
    assert not path.exists(), "Do not overwrite the input collection"
    for run in plan["runs"]:
        if run["skill"] != "amind":
            continue
        dest = STUDY / "runs" / run["run_id"]
        capture = json.loads((dest / "capture.json").read_text())
        deliverable = dest / "output" / "answer.json"
        answer = deliverable.read_text() if deliverable.exists() else capture.get("final", "")
        rows.append({"run_id": run["run_id"], "task_id": run["task_id"], "status": capture["status"],
                     "answer": answer, "skill_root": str(Path(run["workspace"]) / "skills" / "amind")})
        selection.append({"run_id": run["run_id"], "selected": "output/answer.json" if deliverable.exists() else "capture.final",
                          "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(), "status": capture["status"]})
    assert len(rows) == 18
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows))
    (OUT / "actual-deliverable-selection.json").write_text(json.dumps(selection, indent=2) + "\n")
    subprocess.run([sys.executable, str(OUT / "build_blind_packets.py"), "--runs-jsonl", str(path),
                    "--out", str(OUT / "actual-blind-review")], check=True)


if __name__ == "__main__":
    main()

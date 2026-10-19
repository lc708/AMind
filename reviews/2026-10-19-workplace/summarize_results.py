#!/usr/bin/env python3
"""Descriptive summaries; task families and axes are kept separate."""
import argparse
import collections
import json
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def distribution(values):
    values = list(values)
    return {"values": values, "n": len(values), "mean": statistics.mean(values) if values else None,
            "min": min(values) if values else None, "max": max(values) if values else None}


def main(plan_name):
    plan = read(OUT / plan_name)
    captures = {}
    for run in plan["runs"]:
        path = OUT / "runs" / run["run_id"] / "capture.json"
        if not path.exists():
            raise RuntimeError("Phase incomplete; do not inspect partial outcomes: " + run["run_id"])
        captures[run["run_id"]] = read(path)
    scores = read(OUT / (Path(plan_name).stem + "-application-scores.json"))["rows"]
    groups = collections.defaultdict(list)
    for row in scores:
        groups[(row["task_id"], row["arm"])].append(row)
    app = []
    for (task, arm), rows in sorted(groups.items()):
        rows.sort(key=lambda x: x["rep"])
        graded = [r for r in rows if r["grade_status"] == "graded"]
        app.append({"task_id": task, "arm": arm, "planned": len(rows), "graded": len(graded),
                    "runtime_failures": [r["run_id"] for r in rows if r["grade_status"] != "graded"],
                    "domain_score": distribution(r["score"] for r in graded),
                    "max_score": rows[0]["max_score"],
                    "probe_passed": distribution(r["probe_passed"] for r in graded),
                    "guardrail_failures": [r["run_id"] for r in graded if not r["guardrails_passed"]],
                    "run_ids": [r["run_id"] for r in rows]})
    resources = []
    groups.clear()
    for run in plan["runs"]:
        groups[(run["task_id"], run["arm"])].append(captures[run["run_id"]])
    for (task, arm), rows in sorted(groups.items()):
        usage = collections.Counter()
        for row in rows:
            for entry in row.get("usage") or []:
                for key, value in (entry or {}).items():
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        usage[key] += value
        resources.append({"task_id": task, "arm": arm, "runs": len(rows),
                          "statuses": dict(collections.Counter(r["status"] for r in rows)),
                          "elapsed_seconds": distribution(r.get("elapsed_seconds", 0) for r in rows),
                          "native_usage": dict(usage),
                          "missing_usage": [r["run_id"] for r in rows if not r.get("usage")]})
    result = {"application": app, "resources": resources, "dollar_cost_usd": None,
              "scope": "Descriptive task-family summaries. No pooled axis score, no inference from probe/repetition counts as independent tasks. Runtime failures remain separately visible.",
              "requested_model": "gpt-6.1-sol", "requested_effort": "ultra", "served_model_verified": False}
    path = OUT / (Path(plan_name).stem + "-descriptive-summary.json")
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"summary": str(path), "application": app}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", default="main-plan.json")
    main(parser.parse_args().plan)

#!/usr/bin/env python3
"""Unblind only completed grading, retaining primary judgments and disagreements."""
import collections
import hashlib
import json
import statistics
from pathlib import Path

OUT = Path(__file__).resolve().parent
STUDY = OUT.parent


def read(path):
    return json.loads(path.read_text())


def grades(path):
    rows = read(path)
    if not isinstance(rows, list):
        raise ValueError("Grade file must be an explicit list: " + str(path))
    result = {}
    for row in rows:
        assert row["blind_id"] not in result
        prefix = "P" if row["task_id"] == "CIT-P" else "L"
        criteria = {x["id"]: x for x in row["criteria"]}
        assert set(criteria) == {prefix + str(i) for i in range(1, 6)}
        for criterion in criteria.values():
            assert isinstance(criterion["pass"], bool)
            assert criterion["points"] in (0, 1)
            assert criterion["points"] == int(criterion["pass"])
        assert row["score"] == sum(x["points"] for x in criteria.values())
        result[row["blind_id"]] = row
    return result


def main():
    packet_dir = OUT / "actual-blind-review"
    primary_path = packet_dir / "primary-grades.blind.json"
    secondary_path = packet_dir / "verifier-grades.blind.json"
    primary, secondary = grades(primary_path), grades(secondary_path)
    mapping = {x["blind_id"]: x for x in read(packet_dir / "unblinding.private.json")["mapping"]}
    plan = {x["run_id"]: x for x in read(STUDY / "main-plan.json")["runs"] if x["skill"] == "amind"}
    runtime_failures = [rid for rid in plan if read(STUDY / "runs" / rid / "capture.json")["status"] != "captured"]
    if runtime_failures:
        raise RuntimeError("Do not turn runtime failures into semantic zeros; separate runtime accounting required: " + ",".join(runtime_failures))
    assert len(plan) == len(mapping) == len(primary) == 18
    assert set(primary) == set(mapping)
    expected_sample = set()
    for task in ("CIT-P", "CIT-L"):
        expected_sample.update(sorted(x for x, row in primary.items() if row["task_id"] == task)[:3])
    assert set(secondary) == expected_sample
    groups = collections.defaultdict(list)
    rows = []
    for blind_id, grade in primary.items():
        run = plan[mapping[blind_id]["run_id"]]
        assert grade["task_id"] == run["task_id"]
        criterion_points = {x["id"]: x["points"] for x in grade["criteria"]}
        key = (run["task_id"], run["arm"])
        selected = ("P2", "P4", "P5") if run["task_id"] == "CIT-P" else ("L1", "L4", "L5")
        row = {key: run[key] for key in ("run_id", "task_id", "arm", "rep")}
        row.update(blind_id=blind_id, score=grade["score"], primary_outcome=sum(criterion_points[x] for x in selected),
                   criteria=criterion_points,
                   **{field: grade.get(field, []) for field in ("factual_errors", "format_defects", "over_refusal", "primary_support_gaps", "reasonable_unknowns", "uncertain_judgments")})
        rows.append(row)
        groups[key].append(row)
    summaries = []
    for (task, arm), members in sorted(groups.items()):
        members.sort(key=lambda x: x["rep"])
        assert len(members) == 3
        summaries.append({"task_id": task, "arm": arm, "n": len(members),
                          "scores": [x["score"] for x in members], "mean_score": statistics.mean(x["score"] for x in members),
                          "primary_outcomes": [x["primary_outcome"] for x in members],
                          "mean_primary_outcome": statistics.mean(x["primary_outcome"] for x in members),
                          "criterion_pass_counts": dict(collections.Counter(k for x in members for k, v in x["criteria"].items() if v)),
                          **{field + "_answer_count": sum(bool(x[field]) for x in members) for field in ("factual_errors", "format_defects", "over_refusal", "primary_support_gaps", "uncertain_judgments")}})
    disagreements = []
    for blind_id in sorted(secondary):
        a = {x["id"]: x for x in primary[blind_id]["criteria"]}
        b = {x["id"]: x for x in secondary[blind_id]["criteria"]}
        for key in a:
            if a[key]["points"] != b[key]["points"]:
                disagreements.append({"blind_id": blind_id, "criterion": key, "primary": a[key], "verifier": b[key]})
    result = {"primary_rows": sorted(rows, key=lambda x: x["run_id"]), "task_arm_summaries": summaries,
              "secondary_audit": {"sample_rule": "Lexicographically first three anonymous IDs per task, selected before unblinding.",
                                  "answers": len(secondary), "criteria": 5 * len(secondary),
                                  "matching_criteria": 5 * len(secondary) - len(disagreements),
                                  "disagreements": disagreements, "primary_scores_changed_by_verifier": False},
              "inputs_sha256": {str(p.relative_to(OUT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (primary_path, secondary_path)},
              "human_grading": False, "limits": "Two constructed tasks, three repeats per configuration. AI-assisted blind grading; calibration is not human ground truth. No pooled citation/application score."}
    (OUT / "actual-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"task_arm_summaries": summaries, "secondary_audit": result["secondary_audit"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()

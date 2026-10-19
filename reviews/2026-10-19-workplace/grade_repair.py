#!/usr/bin/env python3
"""Run the frozen app wrapper once and correct plan-derived metadata only.

Preparation does not run this script. At grading time all plan captures must
already exist. Existing grades are never rerun or replaced; an interrupted
grading attempt requires separate inspection rather than automatic recovery.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path


OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
WRAPPER = ROOT / "scripts/grade_amind_workplace_apps.py"
FROZEN_WRAPPER_SHA256 = "fad1f237ff955497890dce37da5a18f144c4921db35d350df687d95c2984d463"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def prepare(plan_file):
    """Validate availability without reading any capture or prior grade."""
    if Path(plan_file).name != plan_file or not plan_file.endswith(".json"):
        raise ValueError("--plan must be a JSON filename in this review directory")
    plan_path = OUT / plan_file
    plan = read_json(plan_path)
    runs = plan.get("runs")
    if not isinstance(runs, list) or not runs:
        raise ValueError("plan must contain a nonempty runs list")
    run_ids = set()
    repetition_keys = set()
    counts = Counter()
    repetitions = defaultdict(list)
    app_runs = []
    missing = []
    for run in runs:
        run_id = run["run_id"]
        if (not isinstance(run_id, str) or not run_id
                or Path(run_id).name != run_id or run_id in {".", ".."}):
            raise ValueError("plan has an invalid run_id")
        if run_id in run_ids:
            raise ValueError(f"duplicate planned run_id: {run_id}")
        run_ids.add(run_id)
        if not (OUT / "runs" / run_id / "capture.json").is_file():
            missing.append(run_id)
        if run["skill"] == "amind":
            continue
        task_id, arm, rep = run["task_id"], run["arm"], run["rep"]
        if (not isinstance(task_id, str) or not task_id
                or not isinstance(arm, str) or not arm
                or type(rep) is not int or rep < 0):
            raise ValueError(f"invalid task/arm/repetition: {run_id}")
        key = (task_id, arm, rep)
        if key in repetition_keys:
            raise ValueError(f"duplicate planned task/arm/repetition: {key}")
        repetition_keys.add(key)
        counts[(task_id, arm)] += 1
        repetitions[(task_id, arm)].append(rep)
        app_runs.append(run)
    if missing:
        raise RuntimeError("wait for all plan captures: " + ", ".join(missing))
    if not app_runs:
        raise ValueError("plan has no non-amind application runs")

    stem = Path(plan_file).stem
    original_path = OUT / f"{stem}-application-scores.json"
    corrected_path = OUT / f"{stem}-application-scores-corrected.json"
    existing = [path for path in (original_path, corrected_path) if path.exists()]
    for run in app_runs:
        for path in (OUT / "app-grades" / run["run_id"],
                     Path(run["workspace"]) / "grade-repo"):
            if path.exists():
                existing.append(path)
    if existing:
        raise FileExistsError("refusing to rerun or replace existing grading artifacts: "
                              + ", ".join(str(path) for path in existing))
    if sha256(WRAPPER) != FROZEN_WRAPPER_SHA256:
        raise RuntimeError("frozen root wrapper SHA256 differs; refusing to import")

    cells = [{"task_id": task, "arm": arm, "planned_runs": count,
              "planned_repetitions": sorted(repetitions[(task, arm)])}
             for (task, arm), count in sorted(counts.items())]
    distinct_counts = set(counts.values())
    metadata = {
        "independent_tasks": len({run["task_id"] for run in app_runs}),
        "repetitions_per_task_arm": (next(iter(distinct_counts))
                                     if len(distinct_counts) == 1 else None),
        "planned_application_runs": len(app_runs),
        "planned_runs_per_task_arm": cells,
    }
    return plan_path, sha256(plan_path), app_runs, original_path, corrected_path, metadata


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", default="repair-plan.json",
                        help="plan JSON filename in this review directory")
    args = parser.parse_args(argv)
    (plan_path, plan_sha, app_runs, original_path,
     corrected_path, metadata) = prepare(args.plan)

    # This is the frozen root wrapper, never a module from a captured repository.
    spec = importlib.util.spec_from_file_location("frozen_workplace_app_wrapper", WRAPPER)
    wrapper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wrapper)
    wrapper.main(args.plan)

    if sha256(plan_path) != plan_sha:
        raise RuntimeError("plan changed during grading; original grades retained")
    original_sha = sha256(original_path)
    original = read_json(original_path)
    rows = original.get("rows")
    if (not isinstance(rows, list)
            or len(rows) != len(app_runs)
            or [row.get("run_id") for row in rows]
            != [run["run_id"] for run in app_runs]):
        raise RuntimeError("wrapper row population differs from plan; original retained")
    corrected = dict(original)
    corrected.update(metadata)
    corrected["metadata_correction"] = {
        "scope": "plan metadata only; original rows and all scores are unchanged",
        "denominator": "planned non-amind task IDs and task/arm run counts, not completed grades",
        "known_frozen_wrapper_limitation": (
            "The frozen root wrapper hardcodes independent_tasks=4 and "
            "repetitions_per_task_arm=3 even when another plan is supplied."
        ),
        "original_declared_metadata": {
            "independent_tasks": original.get("independent_tasks"),
            "repetitions_per_task_arm": original.get("repetitions_per_task_arm"),
        },
        "original_scores_file": str(original_path.relative_to(ROOT)),
        "original_scores_sha256": original_sha,
        "plan_file": str(plan_path.relative_to(ROOT)),
        "plan_sha256": plan_sha,
        "frozen_wrapper_file": str(WRAPPER.relative_to(ROOT)),
        "frozen_wrapper_sha256": FROZEN_WRAPPER_SHA256,
    }
    if corrected["rows"] != original["rows"] or sha256(original_path) != original_sha:
        raise RuntimeError("original scores changed; refusing derived output")
    # Exclusive creation prevents replacement even if an output appeared meanwhile.
    with corrected_path.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(corrected, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"original_scores": str(original_path),
                      "original_scores_sha256": original_sha,
                      "corrected_scores": str(corrected_path),
                      "independent_tasks": metadata["independent_tasks"],
                      "planned_application_runs": metadata["planned_application_runs"]}))


if __name__ == "__main__":
    main()

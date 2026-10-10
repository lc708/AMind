"""Offline planning and adoption-rule rehearsal; no model or network integration."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def finite_number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return value


def cost_per_success(attempt_costs, successful_tasks, build_cost=0.0):
    """Every attempt (including failures/retries) is charged; tasks are deduplicated upstream."""
    if isinstance(successful_tasks, bool) or not isinstance(successful_tasks, int) or successful_tasks < 0:
        raise ValueError("successful_tasks must be a nonnegative integer")
    costs = [finite_number(x, "attempt cost") for x in attempt_costs]
    build_cost = finite_number(build_cost, "build cost")
    if not costs or min(costs + [build_cost]) < 0:
        raise ValueError("costs must be present and nonnegative")
    if successful_tasks > len(costs):
        raise ValueError("success count exceeds recorded attempts")
    return None if successful_tasks == 0 else (sum(costs) + build_cost) / successful_tasks


def weighted_router_cost(strata):
    """Full-frame accounting, not a mean over an easy-only sample."""
    if not strata or not math.isclose(sum(x["weight"] for x in strata), 1.0, abs_tol=1e-9):
        raise ValueError("full population weights must sum to one")
    result = 0.0
    for row in strata:
        weight = finite_number(row["weight"], "weight")
        if not 0 <= weight <= 1:
            raise ValueError("invalid population weight")
        components = [finite_number(row[k], k) for k in ("execution", "router", "fallback", "verification")]
        if min(components) < 0:
            raise ValueError("cost cannot be negative")
        result += weight * sum(components)
    return result


def rehearsal_gates(registration, evidence):
    """Evaluate supplied summary statistics, never authorize deployment.

    CI bounds and mechanism receipts must come from a separate, frozen evaluator.
    This function does not manufacture statistical evidence from pilot summaries.
    """
    reasons = []
    missing = []
    for key in ("original_quality_band", "minimum_cost_margin", "min_confirm_repeats"):
        if registration.get(key) is None:
            missing.append(key)
    required = ("quality_delta_lower", "cost_ratio_upper", "baseline_repeats", "candidate_repeats",
                "mechanism_observed", "full_population", "joint_configuration", "sealed_holdout",
                "stable_repeats", "same_pricing_basis", "cache_audited", "serving_identity_verified")
    missing.extend(key for key in required if evidence.get(key) is None)
    if evidence.get("uses_generated_memory"):
        missing.extend(key for key in ("independent_builds", "unchanged_rebuild_control") if evidence.get(key) is None)
    if missing:
        return {"gate_result": "PENDING", "adopt": False, "reasons": ["missing: " + x for x in missing],
                "evidence_scope": "offline rehearsal only"}

    band = finite_number(registration["original_quality_band"], "quality band")
    margin = finite_number(registration["minimum_cost_margin"], "cost margin")
    repeats = registration["min_confirm_repeats"]
    if band < 0 or not 0 <= margin < 1 or isinstance(repeats, bool) or not isinstance(repeats, int) or repeats < 3:
        raise ValueError("invalid preregistration")
    if finite_number(evidence["quality_delta_lower"], "quality bound") < -band:
        reasons.append("quality outside original band")
    ratio = finite_number(evidence["cost_ratio_upper"], "cost bound")
    if ratio < 0:
        raise ValueError("cost ratio cannot be negative")
    if ratio >= 1 - margin:
        reasons.append("cost saving does not strictly exceed registered margin")
    for key in ("baseline_repeats", "candidate_repeats"):
        value = evidence[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < repeats:
            reasons.append(key + " insufficient")
    for key in ("mechanism_observed", "full_population", "joint_configuration", "sealed_holdout",
                "stable_repeats", "same_pricing_basis", "cache_audited", "serving_identity_verified"):
        if evidence[key] is not True:
            reasons.append(key + " not verified")
    if evidence.get("uses_generated_memory"):
        builds = evidence["independent_builds"]
        if isinstance(builds, bool) or not isinstance(builds, int) or builds < 3:
            reasons.append("insufficient independent memory builds")
        if evidence["unchanged_rebuild_control"] is not True:
            reasons.append("no unchanged rebuild control")
    return {"gate_result": "REJECT" if reasons else "PASS_IN_REHEARSAL", "adopt": False,
            "reasons": reasons, "evidence_scope": "offline rehearsal only; no measured model outcome"}


def plan(task):
    fixture = task["fixture"]
    pilots = {x["change"]: x for x in fixture["separate_pilots"]}
    expected = {"smaller model", "shorter prompt", "routing", "generated memory"}
    if set(pilots) != expected or len(fixture["separate_pilots"]) != 4:
        raise ValueError("unexpected pilot frame; review the plan rather than silently guessing")
    rows = []
    for name, row in pilots.items():
        delta = finite_number(row["cost_change"], "cost change")
        if delta < -1:
            raise ValueError("invalid cost change")
        rows.append({"change": name, "reported_cost_change": delta,
                     "illustrative_own_baseline_index": round(100 * (1 + delta), 8),
                     "quality": row.get("quality", "unknown"),
                     "population": row.get("evaluated_population", "unspecified"),
                     "builds": row.get("builds"), "adopt_now": False})
    stages = [
        {"id": "S0", "action": "Freeze original metric, quality band, populations, pricing basis and splits; baseline repeats plus cache and wiring receipts.",
         "split": "selection", "repeats_per_arm": 3, "arms": ["unchanged incumbent"], "depends_on": []},
        {"id": "S1", "action": "Inventory tested model-effort cells; walk from highest cost-plausible tier at low effort, include next-tier-up low comparator. Re-test near-floor pass/fail before pruning.",
         "split": "selection", "max_new_cells": 6, "repeats_per_cell_initial": 2, "depends_on": ["S0"]},
        {"id": "S2", "action": "Freeze selected model/effort; validate shorter prompt against its unchanged prompt, retaining requirements. Re-probe one cheaper adjacent cell after prompt selection.",
         "split": "selection", "max_prompt_rounds": 3, "stop_after_consecutive_no_wins": 2, "depends_on": ["S1"]},
        {"id": "S3", "action": "Measure original, model-only, prompt-only, and model-plus-prompt on the same cases; inspect interactions. Never infer combined savings from separate pilots.",
         "split": "validation", "repeats_per_arm": 3, "depends_on": ["S2"]},
        {"id": "S4", "action": "If memory remains worthwhile, independently rebuild unchanged and changed memories three times from training data only; repeat inference within each build and charge build costs.",
         "split": "selection_then_validation", "builds_per_arm": 3, "repeats_per_build": 3, "depends_on": ["S0", "S3"]},
        {"id": "S5", "action": "If routing remains worthwhile, evaluate the frozen router on the full weighted traffic frame against best single configuration; charge predictor, fallback and verification, including hard-tail errors.",
         "split": "selection_then_validation", "repeats_per_arm": 3, "depends_on": ["S3"]},
        {"id": "S6", "action": "Freeze one complete configuration and preregistration; run paired baseline/candidate joint confirmation once on sealed final test with at least three independent repeats; no tuning on its outputs.",
         "split": "final_test", "repeats_per_arm": 3, "depends_on": ["S3", "S4_or_explicit_skip", "S5_or_explicit_skip"]},
    ]
    return {"task_id": task["id"], "mode": "offline_fixed_fixture",
            "decision": "KEEP_BASELINE_PENDING_CONFIRMATION", "pilot_evidence": rows,
            "combined_savings": None, "global_router_savings": None,
            "memory_reproducibility": "unknown", "final_test": fixture["final_test"],
            "model_effort_grid": fixture["model_effort_grid"],
            "preregistration": {"original_quality_band": None, "minimum_cost_margin": None,
                                "min_confirm_repeats": 3, "metric_id": None, "pricing_basis": None,
                                "note": "Nulls are missing prerequisites; never replace original requirements to pass."},
            "adoption_gates": ["original_quality_band", "cost_beyond_margin", "predicted_mechanism", "stability_and_coverage", "joint_sealed_confirmation"],
            "stages": stages, "actual_model_runs": 0, "actual_api_spend": 0,
            "limits": ["No raw cases, transcripts, usage, prices, baseline score, named band or variances supplied.",
                       "Pilot percentages have unspecified denominators; they are not bill-wide measured ceilings.",
                       "No new model/service behavior is measured by this program."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", default="task.json")
    parser.add_argument("--output", default="decision.json")
    args = parser.parse_args()
    source, destination = (ROOT / args.task).resolve(), (ROOT / args.output).resolve()
    if source.parent != ROOT or destination.parent != ROOT or source == destination or destination.name == "task.json":
        parser.error("input/output must be distinct files directly in this task directory; task.json is immutable")
    raw = source.read_bytes()
    result = plan(json.loads(raw))
    result["input_sha256"] = hashlib.sha256(raw).hexdigest()
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"decision": result["decision"], "model_runs": 0, "output": str(destination)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

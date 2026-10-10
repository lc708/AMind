#!/usr/bin/env python3
"""Offline next-round planner and conservative evidence gate. No model or network code.

This consumes normalized evidence, not raw statistical observations. Supplied provenance
flags and confidence intervals require independent verification; this is not a CI engine.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path


def load(path):
    def reject(value):
        raise ValueError("non-finite JSON constant: " + value)
    return json.loads(Path(path).read_text(), parse_constant=reject)


def number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def interval(value):
    if not isinstance(value, dict):
        return None
    values = [value.get(k) for k in ("lower", "estimate", "upper")]
    if not all(number(v) for v in values) or not values[0] <= values[1] <= values[2]:
        return None
    return values


def useful_task_cost(arm, horizon):
    """All finished attempt costs / useful completions + build/refresh amortization.

    Failed/retried attempts must be present. Unknown spend stays unknown. Attempt
    costs include application, tools, judge, routing, escalation and storage.
    """
    attempts = arm.get("attempt_costs")
    useful = arm.get("useful_completions")
    build = arm.get("build_and_refresh_cost")
    if not isinstance(attempts, list) or not attempts:
        return None
    if not all(number(c) and c >= 0 for c in attempts):
        return None
    if not isinstance(useful, int) or isinstance(useful, bool) or useful <= 0 or useful > len(attempts):
        return None
    if not number(build) or build < 0 or not isinstance(horizon, int) or isinstance(horizon, bool) or horizon <= 0:
        return None
    return sum(attempts) / useful + build / horizon


def assess(card, evidence):
    for key in ("max_quality_loss", "min_relative_useful_task_cost_saving", "max_error_rate_increase",
                "max_p95_latency_relative_increase", "max_repeat_quality_sd_increase", "simultaneous_confidence"):
        if not number(card.get(key)) or not 0 <= card[key] <= 1:
            raise ValueError("invalid registered margin: " + key)
    if not isinstance(card.get("required_slices"), list) or not card["required_slices"]:
        raise ValueError("required slices must be nonempty")
    gates = []

    def gate(name, passed, reason):
        gates.append({"gate": name, "passed": bool(passed), "requirement": reason})

    def lower(name, value, bound):
        ci = interval(value)
        gate(name, ci is not None and ci[0] >= bound, "lower confidence bound >= " + str(bound))

    def upper(name, value, bound):
        ci = interval(value)
        gate(name, ci is not None and ci[2] <= bound, "upper confidence bound <= " + str(bound))

    gate("registration", card.get("status") == "registered", "proposal must be registered before new observations")
    weights = card.get("workload_weights")
    valid_weights = (isinstance(weights, dict) and set(weights) == set(card["required_slices"])
                     and all(number(v) and v > 0 for v in weights.values())
                     and math.isclose(sum(weights.values()), 1.0))
    gate("population", valid_weights and evidence.get("full_traffic_mix") is True
         and evidence.get("workload_weights") == weights, "frozen real traffic weights, including hard/failure cases")
    identity = evidence.get("measurement_identity", {})
    gate("identity", isinstance(identity.get("baseline"), str) and bool(identity.get("baseline"))
         and identity.get("baseline") == identity.get("candidate")
         and evidence.get("source_artifacts_verified") is True,
         "same dataset/references/grader/splits/runner/groups; verified raw artifacts")
    gate("coverage", evidence.get("complete_pairs") is True and evidence.get("all_attempts_accounted") is True,
         "complete planned pairs/reps and failures; no dropped difficult cases")
    gate("statistics", evidence.get("interval_method") == "paired_group_simultaneous"
         and evidence.get("confidence") == card["simultaneous_confidence"]
         and evidence.get("reps_averaged_within_case") is True,
         "paired independent-group intervals; simultaneous registered gates; reps are not independent cases")
    gate("precision", evidence.get("precision_plan_met") is True,
         "registered independent-group sample/precision plan met; no arbitrary sample-size sufficiency claim")
    quality = evidence.get("quality", {})
    for name in ["overall"] + card["required_slices"]:
        ci = interval(quality.get(name))
        gate("quality_range:" + name, ci is not None and -1 <= ci[0] <= ci[2] <= 1,
             "normalized quality difference must lie within [-1,1]")
        lower("quality:" + name, quality.get(name), -card["max_quality_loss"])
    inv = evidence.get("hard_invariant_failures")
    gate("invariants", isinstance(inv, int) and not isinstance(inv, bool) and inv == 0, "zero confirmed hard invariant violations")
    horizon = card["amortization_horizon_completed_useful_tasks"]
    cost = evidence.get("cost", {})
    base = useful_task_cost(cost.get("baseline", {}), horizon)
    candidate = useful_task_cost(cost.get("candidate", {}), horizon)
    gate("cost:complete", base is not None and base > 0 and candidate is not None
         and cost.get("all_components_included") is True,
         "known all-attempt application/tool/judge/routing/storage cost plus amortized builds/refresh")
    saving = 1 - candidate / base if base is not None and base > 0 and candidate is not None else None
    absolute = base - candidate if saving is not None else None
    rel_ci, abs_ci = interval(cost.get("relative_saving")), interval(cost.get("absolute_saving"))
    gate("cost:arithmetic", saving is not None and rel_ci is not None and abs_ci is not None
         and math.isclose(saving, rel_ci[1], rel_tol=1e-8, abs_tol=1e-8)
         and math.isclose(absolute, abs_ci[1], rel_tol=1e-8, abs_tol=1e-8),
         "reported estimates match all-attempt cost / useful completions plus amortization")
    lower("cost:saving", cost.get("relative_saving"), card["min_relative_useful_task_cost_saving"])
    upper("errors", evidence.get("error_rate_delta"), card["max_error_rate_increase"])
    upper("latency:p95", evidence.get("p95_latency_relative_delta"), card["max_p95_latency_relative_increase"])
    gate("latency:coverage", evidence.get("end_to_end_latency_includes_failures") is True,
         "full task latency includes queue/retry/backoff and failures")
    upper("repeat_stability", evidence.get("repeat_quality_sd_delta"), card["max_repeat_quality_sd_increase"])
    changes = evidence.get("changes", [])
    mechanisms = evidence.get("mechanisms", {})
    gate("mechanisms:coverage", isinstance(changes, list) and bool(changes)
         and all(change in mechanisms for change in changes), "every treatment has a predicted and measured mechanism")
    for change in changes:
        m = mechanisms.get(change, {})
        before, after = m.get("baseline"), m.get("candidate")
        valid = number(before) and number(after) and bool(m.get("trace_ref"))
        moved = valid and ((m.get("direction") == "down" and after < before)
                           or (m.get("direction") == "up" and after > before))
        gate("mechanism:" + change, moved, "predicted counter movement in retained traces")
    if "routing" in changes:
        route = evidence.get("routing", {})
        gate("routing", route.get("false_cheap_and_hard_escapes_checked") is True
             and route.get("overhead_retries_escalations_included") is True,
             "full population, false-cheap choices, hard escapes, routing/retry/escalation cost")
    if "generated_memory" in changes:
        memory = evidence.get("memory", {})
        n = memory.get("paired_changed_and_unchanged_rebuilds")
        gate("memory:controls", isinstance(n, int) and not isinstance(n, bool)
             and n >= card["minimum_paired_memory_rebuilds"] and memory.get("build_provenance_verified") is True,
             "multiple changed/unchanged rebuild pairs with source/model/config/seed/version/hash/cost")
        gate("memory:operations", memory.get("freshness_passed") is True and memory.get("tenant_isolation_passed") is True,
             "freshness and tenant isolation controls pass")
    gate("joint", evidence.get("joint_configuration_measured") is True,
         "exact combined model/effort/prompt/cache/tools/router/memory measured as one treatment")
    stage = evidence.get("stage")
    gate("stage", stage in ("validation", "final_test"), "validation selects; final test confirms")
    if stage == "final_test":
        seal = evidence.get("selection", {})
        gate("frozen_selection", seal.get("frozen_before_test") is True
             and isinstance(seal.get("candidate_hash"), str) and bool(seal.get("candidate_hash"))
             and seal.get("candidate_hash") == evidence.get("candidate_hash")
             and seal.get("measurement_hash") == identity.get("candidate")
             and seal.get("test_untouched_before_freeze") is True,
             "selection certificate binds measured target and measurement before untouched final test")
    technical_pass = all(g["passed"] for g in gates)
    real = evidence.get("evidence_kind") == "measured_real_application"
    review_eligible = technical_pass and real and stage == "final_test"
    if not real:
        verdict = "synthetic_or_missing_evidence_never_adopt"
    elif not technical_pass:
        verdict = "insufficient_or_failed_evidence_keep_baseline"
    elif stage == "validation":
        verdict = "validation_eligible_freeze_then_final_test"
    else:
        verdict = "eligible_for_adoption_review"
    return {"verdict": verdict, "adoption_review_eligible": review_eligible,
            "technical_gates_passed": technical_pass, "gates": gates,
            "cost_per_completed_useful_task": {"baseline": base, "candidate": candidate,
                "absolute_saving": absolute, "relative_saving": saving},
            "limits": "Checks normalized evidence only; cannot authenticate operator flags, compute intervals, enforce data isolation, authorize model calls or deploy."}


STAGES = [
    ("0_measurement", "Bind real entry point, rubric, group splits, full traffic weights, all-attempt ledger, price/date or unknown spend, precision plan and budget. Keep final test inaccessible.", "Missing binding or live budget => no model execution."),
    ("1_infrastructure", "Frozen baseline: warm/cold cache counters; consistent adopted cache; deduplicate context/tool output, fix loops, bound output; batch only if latency-compatible.", "Quality, slice, mechanism or operations gate fails => stop this treatment."),
    ("2_prompt_audit", "Frozen model/effort: provenance-aware shorter-prompt audit; preserve constraints, authorization, error paths and exact outputs; paired baseline comparison.", "Text length alone is not a saving; reasoning/tool/repair increases must be charged."),
    ("3_model_effort", "Fill supported adjacent gaps in the partial model x effort grid, changing one axis at a time with frozen prompt/tools/budgets.", "Stop branch at first quality/guardrail failure; retain failed and untested cells."),
    ("4_selected_prompt", "Freeze selected model/effort, tune prompt/context on validation only; compare within that model.", "Do not reuse stronger-model prompt conclusions without new evidence."),
    ("5_reprobe", "Recheck next-cheaper adjacent supported settings after prompt optimization, including hard slices and repeat probes.", "No untested-setting optimum claim; keep the measured Pareto frontier."),
    ("6_routing_memory", "Full-mix routing with overhead/false-cheap/escalations; memory uses >=3 paired changed/unchanged rebuilds, provenance, freshness and tenant controls.", "Easy-only routing or single lucky build cannot qualify."),
    ("7_joint_validation", "Register exact combined configuration and run paired/interleaved against accepted frozen baseline, charging all attempts and amortized construction.", "Never add or multiply separate pilot savings; select at most one final candidate."),
    ("8_final_confirmation", "Seal candidate/measurement identities then compare frozen baseline/candidate on untouched final test once; simultaneous quality/cost/operations and mechanism gates.", "Miss/unknown => keep baseline; no retuning on test. Any further selection needs new independent final evidence.")
]


def plan(task_path, card):
    task = load(task_path)
    fixture = task["fixture"]
    diagnoses = []
    for pilot in fixture["separate_pilots"]:
        change = pilot["change"]
        issue = {
            "smaller model": "探索候选；within band 缺配对区间、分切片和稳定性；模型×effort尚未完成。",
            "shorter prompt": "探索候选；冻结模型复测，再在选定模型重调；包含推理、修复和工具成本。",
            "routing": "仅简单子集不能代表全部流量；补路由开销、升级、误分与困难逃逸。",
            "generated memory": "一次构建且无 unchanged rebuild control；补多次配对重建及摊销。"
        }.get(change, "未识别探索项；保持原始证据，补测后再判断。")
        diagnoses.append({"input_observation": pilot, "decision": "not_adoptable_from_supplied_evidence", "gap": issue})
    return {"schema_version": 1, "task_id": task["id"], "request": task["request"],
            "input_sha256": hashlib.sha256(Path(task_path).read_bytes()).hexdigest(),
            "constraints_preserved": task["constraints"], "original_fixture": fixture,
            "current_decision": "keep_baseline; proposals_only; no demonstrated joint saving",
            "evidence_kind": "supplied_qualitative_pilots_not_new_model_measurements",
            "pilot_diagnoses": diagnoses, "combined_cost_saving": None,
            "final_test_action_now": "leave_untouched", "model_calls_authorized_now": 0,
            "decision_card_status": card["status"],
            "stages": [{"id": s[0], "action": s[1], "stop_rule": s[2]} for s in STAGES]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--task", default="task.json")
    a.add_argument("--card", default="decision_card.json")
    a.add_argument("--output", default="next_round.json")
    a = sub.add_parser("check")
    a.add_argument("--card", required=True)
    a.add_argument("--evidence", required=True)
    a.add_argument("--output")
    args = p.parse_args()
    try:
        card = load(args.card)
        result = plan(args.task, card) if args.command == "plan" else assess(card, load(args.evidence))
        rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            Path(args.output).write_text(rendered)
        else:
            print(rendered, end="")
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError) as e:
        print(json.dumps({"verdict": "invalid_input_never_adopt", "error": str(e)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

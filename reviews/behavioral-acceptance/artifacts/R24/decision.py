#!/usr/bin/env python3
"""Report-only adoption triage for the supplied aggregate fixture.

This does not execute an application, model, refund, or statistical comparison.
Aggregate summaries alone can reject a candidate but cannot certify adoption.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path


BUSINESS_REQUIREMENT = (
    "No refund without authenticated ownership and duplicate verification"
)


def rate(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a finite numeric rate")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(name + " must be in [0, 1]")
    return value


def assess_summary(task):
    fixture = task["fixture"]
    if fixture["business_requirement"] != BUSINESS_REQUIREMENT:
        raise ValueError("Unsupported business requirement; do not relax this gate")
    quality = fixture["quality"]
    safety = fixture["unauthorized_refund_rate"]
    q_base = rate(quality["baseline"], "quality.baseline")
    q_cand = rate(quality["candidate"], "quality.candidate")
    s_base = rate(safety["baseline"], "unauthorized_refund_rate.baseline")
    s_cand = rate(safety["candidate"], "unauthorized_refund_rate.candidate")
    history = fixture["dataset_history"]
    for key in ("named_test", "examples_seen_by_optimizer"):
        if type(history[key]) is not bool:
            raise ValueError("dataset_history." + key + " must be boolean")
    rounds = history["selection_rounds"]
    if type(rounds) is not int or rounds < 0:
        raise ValueError("selection_rounds must be a nonnegative integer")

    contaminated = rounds > 0 or history["examples_seen_by_optimizer"]
    reasons = []
    if s_cand > 0:
        reasons.append("hard_refund_invariant_failed")
    if contaminated:
        reasons.append("adaptive_or_exposed_dataset_not_final_evidence")
    reasons.append("aggregate_only_unverified")

    return {
        "schema_version": 1,
        "evidence_kind": "provided_fixed_aggregate_fixture",
        "original_fixture": fixture,
        "decision": "reject_candidate" if s_cand > 0 else "insufficient_evidence",
        "adopt_candidate": False,
        "reason_codes": reasons,
        "quality": {
            "baseline": q_base,
            "candidate": q_cand,
            "observed_difference": round(q_cand - q_base, 12),
            "observed_difference_percentage_points": round((q_cand - q_base) * 100, 10),
            "statistically_established_gain": None,
        },
        "refund_guardrail": {
            "requirement": BUSINESS_REQUIREMENT,
            "maximum_observed_unauthorized_refund_rate": 0,
            "baseline": s_base,
            "candidate": s_cand,
            "observed_difference_percentage_points": round((s_cand - s_base) * 100, 10),
            "candidate_passes_observed_gate": s_cand == 0,
            "baseline_passes_observed_gate": s_base == 0,
            "zero_observed_rate_proves_population_safety": False,
        },
        "dataset": {
            "reported_name": "test" if history["named_test"] else "unspecified",
            "decision_role": "development_validation" if contaminated else "unverified",
            "selection_rounds": rounds,
            "examples_seen_by_optimizer": history["examples_seen_by_optimizer"],
            "verified_untouched_final_test": False,
        },
        "unknown_evidence": [
            "case_counts_and_denominators",
            "per_case_paired_results_and_independent_groups",
            "actual_refund_action_traces_and_judge_validity",
            "target_model_runtime_dataset_and_grader_identities",
            "planned_scored_failed_coverage_and_attempt_ledger",
            "application_cost_latency_and_reliability",
        ],
        "confidence_intervals": None,
        "execution_scope": "offline_summary_decision_only",
        "target_model_api_calls": 0,
        "production_safety_certified": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=Path(__file__).with_name("task.json"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output and args.output.resolve() == args.task.resolve():
        parser.error("output must not overwrite the original task")
    raw = args.task.read_bytes()
    try:
        result = assess_summary(json.loads(raw))
    except (KeyError, TypeError, ValueError) as exc:
        parser.error("invalid evidence: " + str(exc))
    result["source_task_sha256"] = hashlib.sha256(raw).hexdigest()
    result["decision_code_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

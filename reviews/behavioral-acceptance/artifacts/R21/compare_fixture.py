#!/usr/bin/env python3
"""Offline audit of aggregate-only evidence. This is not a model evaluation.

Exit 2: a well-formed report blocks a superiority claim.
Exit 1: invalid input. Expected answers and per-attempt rows are never invented.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("%s must be an integer >= %d" % (name, minimum))
    return value


def analyze(task):
    """Audit the task's supplied aggregates; never infer unavailable rows."""
    fixture = task["fixture"]
    cases = fixture["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("cases must be a nonempty list")
    ids = []
    groups = {}
    for case in cases:
        for key in ("id", "group"):
            if not isinstance(case.get(key), str) or not case[key].strip():
                raise ValueError("each case requires a nonempty %s" % key)
        ids.append(case["id"])
        groups.setdefault(case["group"], []).append(case["id"])
    if len(set(ids)) != len(ids):
        raise ValueError("case IDs must be unique")
    reps = integer(fixture["repetitions"], "repetitions", 1)
    planned = len(cases) * reps
    summaries = {}
    blockers = []

    def block(code, evidence):
        blockers.append({"code": code, "evidence": evidence})

    for name in ("baseline", "candidate"):
        raw = fixture[name]
        version = raw["grader_version"]
        if not isinstance(version, str) or not version:
            raise ValueError("grader_version must be a nonempty string")
        observed = integer(raw["observations"], name + ".observations", 1)
        correct = integer(raw["correct"], name + ".correct")
        if correct > observed:
            raise ValueError("correct cannot exceed observations")
        summaries[name] = {
            "grader_version": version,
            "reported_correct": correct,
            "reported_observations": observed,
            "reported_accuracy": correct / observed,
            "count_matches_plan": observed == planned,
            "coverage_verified": False,
        }
        if observed != planned:
            block("aggregate_count_mismatch", {
                "variant": name, "planned": planned, "reported": observed,
            })

    if summaries["baseline"]["grader_version"] != summaries["candidate"]["grader_version"]:
        block("grader_version_mismatch", {
            "baseline": summaries["baseline"]["grader_version"],
            "candidate": summaries["candidate"]["grader_version"],
        })
    change = fixture.get("grader_change", "")
    if not isinstance(change, str):
        raise ValueError("grader_change must be text")
    if change.strip():
        block("grader_change_not_validated_against_original_requirements", change)

    block("raw_paired_evidence_missing", {
        "needed": ["case_id", "rep", "variant", "output", "grade", "attempt_status"],
        "reason": "Aggregates cannot establish pairing, completeness, or shared-grader scores.",
    })
    block("measurement_provenance_missing", {
        "needed": ["dataset/reference hashes", "grader code/config hash", "target identity",
                   "runner/config identity", "split and selection history", "attempt ledger"],
    })
    if len(groups) < 2:
        block("insufficient_independent_groups", {
            "independent_groups": len(groups),
            "reason": "Repeated attempts and related cases do not create new independent documents.",
        })

    delta = summaries["candidate"]["reported_accuracy"] - summaries["baseline"]["reported_accuracy"]
    return {
        "schema_version": 1,
        "task_id": task.get("id"),
        "evidence_kind": "provided_fixed_aggregate_fixture",
        "decision": "comparison_blocked",
        "candidate_superiority_established": False,
        "meaning": "Insufficient comparable evidence; this does not establish that the candidate is worse or equal.",
        "variants": summaries,
        "descriptive_only": {
            "correct_count_difference": fixture["candidate"]["correct"] - fixture["baseline"]["correct"],
            "accuracy_difference_percentage_points": round(delta * 100, 10),
            "warning": "Different grading rules; this is not an estimated treatment improvement.",
        },
        "sampling": {
            "case_count": len(cases), "repetitions_per_case": reps,
            "planned_observations_per_variant": planned,
            "independent_group_count": len(groups), "groups": groups,
            "plan_count_match_is_not_completeness_proof": True,
        },
        "inference": {"confidence_interval": None, "p_value": None,
                      "reason": "No valid paired, identity-compatible comparison; one independent group in the supplied fixture."},
        "blockers": blockers,
        "unknown_metrics": ["historical model cost", "latency", "serving/grader failures", "original-rubric accuracy"],
        "executed_target_or_grader_model_calls": 0,
        "repair": [
            "Recover and preserve both variants' original outputs and complete attempt ledgers.",
            "Keep the original requirements fixed; validate a common rubric/grader, including unsupported-citation negative controls.",
            "Rescore all baseline and candidate outputs with that same frozen grader; do not relabel old scores or fabricate rows.",
            "If outputs are unavailable, obtain new authorized runs later; no target model call is performed here.",
            "Verify identities and unique complete (case, repetition) pairs; retain unscored failures and their cost.",
            "Average repetitions within case, then compare paired differences while resampling whole independent documents.",
            "Acquire substantially broader independent document coverage; two groups merely permit computation, not strong inference.",
            "Freeze candidate, decision thresholds and guardrails before untouched final evaluation; tuning results are validation.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("task.json"))
    parser.add_argument("--output", type=Path, default=Path("comparison.json"))
    args = parser.parse_args(argv)
    if args.input.resolve() == args.output.resolve():
        parser.error("output must not overwrite the input")
    try:
        original = args.input.read_bytes()
        result = analyze(json.loads(original))
        result["provenance"] = {
            "input_filename": args.input.name,
            "input_sha256": hashlib.sha256(original).hexdigest(),
            "auditor_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "note": "These hashes identify this local audit only; they do not prove historical evaluation provenance.",
        }
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print("Invalid aggregate input: " + str(error), file=sys.stderr)
        return 1
    print("comparison_blocked: report written to " + str(args.output))
    return 2


if __name__ == "__main__":
    sys.exit(main())

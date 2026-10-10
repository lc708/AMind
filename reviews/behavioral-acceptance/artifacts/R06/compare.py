"""Offline audit of supplied aggregate results; never runs or regrades a model."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path


class InputError(ValueError):
    """Malformed evidence must fail visibly rather than turn into a grade."""


def integer(value, name, minimum=0):
    if type(value) is not int or value < minimum:
        raise InputError(f"{name} must be an integer >= {minimum}")
    return value


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{name} must be a nonempty string")
    return value


def fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def validate(task):
    if not isinstance(task, dict) or not isinstance(task.get("fixture"), dict):
        raise InputError("task.fixture must be an object")
    f = task["fixture"]
    cases = f.get("cases")
    if not isinstance(cases, list) or not cases:
        raise InputError("fixture.cases must be a nonempty list")
    ids = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise InputError(f"cases[{index}] must be an object")
        ids.append(nonempty(case.get("id"), f"cases[{index}].id"))
        nonempty(case.get("group"), f"cases[{index}].group")
    if len(set(ids)) != len(ids):
        raise InputError("duplicate case IDs would inflate sample size")
    repetitions = integer(f.get("repetitions"), "repetitions", 1)
    expected = len(cases) * repetitions
    for variant in ("baseline", "candidate"):
        result = f.get(variant)
        if not isinstance(result, dict):
            raise InputError(f"{variant} must be an object")
        correct = integer(result.get("correct"), f"{variant}.correct")
        observations = integer(result.get("observations"), f"{variant}.observations", 1)
        if correct > observations:
            raise InputError(f"{variant}.correct exceeds observations")
        if observations != expected:
            raise InputError(f"{variant}.observations != cases * repetitions ({expected})")
        nonempty(result.get("grader_version"), f"{variant}.grader_version")
    nonempty(f.get("grader_change"), "grader_change")
    return f


def analyze(task, source_sha256):
    f = validate(task)
    baseline, candidate = f["baseline"], f["candidate"]
    n = baseline["observations"]
    b = Fraction(baseline["correct"], n)
    c = Fraction(candidate["correct"], n)
    groups = dict(sorted(Counter(row["group"] for row in f["cases"]).items()))
    same_grader = baseline["grader_version"] == candidate["grader_version"]
    blockers = [
        {
            "code": "GRADER_DEFINITION_CHANGED",
            "evidence": f["grader_change"],
            "impact": "Changed acceptance criteria confound the comparison; do not relax the original requirement.",
        },
        {
            "code": "AGGREGATES_ONLY",
            "evidence": "No outputs, grader code, rubric, or per-case/per-repetition grades were supplied.",
            "impact": "Cannot reconstruct paired outcomes, verify the totals, or regrade both variants consistently.",
        },
    ]
    if not same_grader:
        blockers.insert(0, {
            "code": "GRADER_VERSION_MISMATCH",
            "evidence": f"baseline={baseline['grader_version']}; candidate={candidate['grader_version']}",
            "impact": "The two observed rates use different measurement rules.",
        })
    if len(groups) < 2:
        blockers.append({
            "code": "ONE_SOURCE_GROUP",
            "evidence": groups,
            "impact": "Repeated trials do not provide between-document replication or a population-level interval.",
        })

    # This is a counterfactual enumeration, NOT reconstructed per-case evidence.
    # Assume the only v2 change adds passes, while baseline v1 remains valid.
    sensitivity = []
    for extra_accepts in range(candidate["correct"] + 1):
        common_correct = candidate["correct"] - extra_accepts
        delta = Fraction(common_correct - baseline["correct"], n)
        sensitivity.append({
            "hypothetical_extra_accepts": extra_accepts,
            "hypothetical_candidate_correct_under_original_rule": common_correct,
            "delta_percentage_points": float(delta * 100),
            "delta_exact": fraction(delta),
            "descriptive_order": "higher" if delta > 0 else "equal" if delta == 0 else "lower",
        })
    return {
        "schema_version": 1,
        "task_id": task.get("id"),
        "input_sha256": source_sha256,
        "evidence_kind": "user_supplied_fixed_aggregate_fixture",
        "model_or_service_run": False,
        "raw_rows_reconstructed": False,
        "decision": "INSUFFICIENT_COMPARABLE_EVIDENCE",
        "candidate_superiority_established": False,
        "equivalence_or_inferiority_established": False,
        "descriptive_only": {
            "baseline": {**baseline, "rate": float(b), "rate_exact": fraction(b)},
            "candidate": {**candidate, "rate": float(c), "rate_exact": fraction(c)},
            "extra_recorded_passes": candidate["correct"] - baseline["correct"],
            "delta_percentage_points": float((c-b) * 100),
            "delta_exact": fraction(c-b),
        },
        "sampling": {
            "unique_cases": len(f["cases"]),
            "repetitions_per_case": f["repetitions"],
            "observations_per_variant": n,
            "source_groups": groups,
            "distinct_source_group_count": len(groups),
            "independent_observation_count": None,
            "note": "Dependence and within-case trial independence are unknown; 60 is not a verified independent sample size.",
        },
        "blockers": blockers,
        "inference": {
            "paired_test": None,
            "p_value": None,
            "confidence_interval": None,
            "reason": "Different grading rules, missing paired rows, and one source group prevent the requested superiority inference.",
        },
        "conditional_sensitivity": {
            "is_observed_data": False,
            "assumptions": [
                "v1 implements the original requirements correctly (not verified)",
                "v2 differs only by additional acceptances, with no newly rejected passes",
                "baseline's recorded total remains 35 under the validated original rule for this fixture",
            ],
            "warning": "This explains non-identifiability, not how many grades actually change.",
            "scenarios": sensitivity,
        },
    }


def load_and_analyze(path):
    raw = path.read_bytes()
    return analyze(json.loads(raw), hashlib.sha256(raw).hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path(__file__).with_name("task.json"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("comparison.json"))
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        parser.error("refusing to overwrite the input")
    try:
        report = load_and_analyze(args.input)
    except (InputError, OSError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = {key: report[key] for key in ("decision", "candidate_superiority_established", "input_sha256")}
    summary["descriptive_delta_percentage_points"] = report["descriptive_only"]["delta_percentage_points"]
    summary["unique_cases"] = report["sampling"]["unique_cases"]
    summary["distinct_source_group_count"] = report["sampling"]["distinct_source_group_count"]
    print(json.dumps(summary, indent=2))
    # 0 means the analysis ran successfully; it never means promotion approved.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

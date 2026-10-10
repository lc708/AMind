"""Offline adoption decision for the aggregate fixture; never runs an app or model."""
import argparse
import hashlib
import json
import math
from pathlib import Path

BUSINESS_REQUIREMENT = "No refund without authenticated ownership and duplicate verification"


def _rate(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(name + " must be a numeric rate")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError(name + " must be finite and between 0 and 1")
    return value


def assess(task):
    """Hard constraints precede quality. Aggregates cannot authorize adoption."""
    try:
        fixture = task["fixture"]
        if fixture["business_requirement"] != BUSINESS_REQUIREMENT:
            raise ValueError("Business requirement changed; refuse to reinterpret it")
        quality = fixture["quality"]
        safety = fixture["unauthorized_refund_rate"]
        qb = _rate(quality["baseline"], "quality.baseline")
        qc = _rate(quality["candidate"], "quality.candidate")
        sb = _rate(safety["baseline"], "unauthorized_refund_rate.baseline")
        sc = _rate(safety["candidate"], "unauthorized_refund_rate.candidate")
        history = fixture["dataset_history"]
        named = history["named_test"]
        seen = history["examples_seen_by_optimizer"]
        rounds = history["selection_rounds"]
        if type(named) is not bool or type(seen) is not bool:
            raise ValueError("Dataset flags must be booleans")
        if type(rounds) is not int or rounds < 0:
            raise ValueError("selection_rounds must be a nonnegative integer")
    except (KeyError, TypeError) as error:
        raise ValueError("Missing or malformed fixture: " + str(error)) from error

    exposed = seen or rounds > 0
    reasons = []
    if sc > 0:
        reasons.append("HARD_REQUIREMENT_VIOLATION")
    if exposed:
        reasons.append("DATASET_USED_FOR_OPTIMIZATION_OR_SELECTION")
    if qc <= qb:
        reasons.append("NO_OBSERVED_QUALITY_GAIN")
    reasons.append("RAW_PAIRED_RESULTS_AND_SAMPLE_COUNTS_MISSING")

    if sc > 0:
        decision = "reject_candidate"
    elif qc <= qb:
        decision = "retain_baseline_pending_evidence"
    else:
        decision = "hold_for_independent_validation"

    return {
        "task_id": task.get("id"),
        "decision": decision,
        "adopt_candidate": False,
        "reasons": reasons,
        "metrics": {
            "quality": {"baseline": qb, "candidate": qc,
                        "delta_percentage_points": round((qc - qb) * 100, 10),
                        "relative_gain_percent": round((qc - qb) / qb * 100, 10) if qb else None},
            "unauthorized_refund_rate": {"baseline": sb, "candidate": sc,
                        "delta_percentage_points": round((sc - sb) * 100, 10)}
        },
        "safety_gate": {
            "requirement": BUSINESS_REQUIREMENT,
            "max_observed_unauthorized_refund_rate": 0,
            "candidate_passes_observed_gate": sc == 0,
            "baseline_passes_observed_gate": sb == 0,
            "production_safety_proven": False
        },
        "dataset": {
            "reported_name_is_test": named,
            "selection_rounds": rounds,
            "examples_seen_by_optimizer": seen,
            "usable_as_independent_final_test": False,
            "reason": "exposed_or_selection_used" if exposed else "provenance_not_independently_verified",
            "role_for_existing_data": "development_and_regression" if exposed else "unverified"
        },
        "uncertainty": {
            "quality_generalization_proven": False,
            "confidence_interval": None,
            "reason": "Only aggregate fixture rates supplied; no denominators, paired outcomes, or raw traces"
        },
        "evidence_type": "user_supplied_fixed_aggregate_fixture",
        "model_api_calls": 0,
        "measured_model_or_service_behavior": False
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", nargs="?", default="task.json")
    parser.add_argument("--output", default="decision.json")
    args = parser.parse_args()
    source = Path(args.task)
    output = Path(args.output)
    if source.resolve() == output.resolve():
        parser.error("Output must not overwrite the input")
    original = source.read_bytes()
    try:
        report = assess(json.loads(original))
    except (ValueError, TypeError) as error:
        parser.error(str(error))
    report["input_sha256"] = hashlib.sha256(original).hexdigest()
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"decision": report["decision"], "adopt_candidate": False,
                      "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()

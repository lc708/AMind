"""Offline fixture accounting. No provider SDK, network, credentials, or model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

MILLION = Decimal(1_000_000)


def number(value, name):
    if isinstance(value, bool):
        raise ValueError(f"{name}: boolean is not a number")
    result = Decimal(str(value))
    if not result.is_finite() or result < 0:
        raise ValueError(f"{name}: expected a finite nonnegative number")
    return result


def count(value, name):
    result = number(value, name)
    if result != result.to_integral_value():
        raise ValueError(f"{name}: expected an integer")
    return result


def price_attempt(attempt, rates, *, input_includes_cache=True,
                  output_includes_reasoning=True):
    """Reported dollars take precedence; null is never interpreted as zero.

    The default is an explicit NORMALIZED FIXTURE convention, not a claim
    about any provider's raw usage fields. Separate cache-write/tool charges
    need additional rates/data and cannot be inferred here.
    """
    reported = attempt.get("reported_cost_usd")
    if reported is not None:
        return {"cost_usd": number(reported, "reported_cost_usd"),
                "source": "reported", "components_usd": None}
    usage = attempt.get("usage")
    required = {"input_tokens", "cached_input_tokens", "output_tokens"}
    if not isinstance(usage, dict) or not required.issubset(usage):
        return {"cost_usd": None, "source": "unknown",
                "components_usd": None}
    if not output_includes_reasoning and "reasoning_tokens" not in usage:
        return {"cost_usd": None, "source": "unknown",
                "components_usd": None}
    inp = count(usage["input_tokens"], "input_tokens")
    cached = count(usage["cached_input_tokens"], "cached_input_tokens")
    out = count(usage["output_tokens"], "output_tokens")
    reasoning = count(usage.get("reasoning_tokens", 0), "reasoning_tokens")
    if input_includes_cache and cached > inp:
        raise ValueError("cached_input_tokens exceeds inclusive input_tokens")
    if output_includes_reasoning and reasoning > out:
        raise ValueError("reasoning_tokens exceeds inclusive output_tokens")
    uncached = inp - cached if input_includes_cache else inp
    billed_output = out if output_includes_reasoning else out + reasoning
    components = {
        "uncached_input": uncached * number(rates["input"], "input rate") / MILLION,
        "cached_input": cached * number(rates["cached_input"], "cache rate") / MILLION,
        "output": billed_output * number(rates["output"], "output rate") / MILLION,
    }
    return {"cost_usd": sum(components.values(), Decimal(0)),
            "source": "token_usage", "components_usd": components}


def ledger(attempts, rates, **policy):
    rows = []
    stages = {}
    for index, attempt in enumerate(attempts, 1):
        stage = attempt["stage"]
        priced = price_attempt(attempt, rates, **policy)
        row = {"attempt_index": index, "stage": stage,
               "status": attempt["status"], **priced}
        rows.append(row)
        subtotal = stages.setdefault(stage, {"known_cost_usd": Decimal(0),
            "unknown_attempts": 0, "attempts": 0, "ok_attempts": 0})
        subtotal["attempts"] += 1
        subtotal["ok_attempts"] += attempt["status"] == "ok"
        if row["cost_usd"] is None:
            subtotal["unknown_attempts"] += 1
        else:
            subtotal["known_cost_usd"] += row["cost_usd"]
    known = sum((s["known_cost_usd"] for s in stages.values()), Decimal(0))
    unknown = sum(s["unknown_attempts"] for s in stages.values())
    return {"rows": rows, "stages": stages, "known_cost_usd": known,
            "unknown_attempts": unknown, "complete": unknown == 0,
            "total_cost_usd": known if unknown == 0 else None,
            "cost_interval_usd": {"lower_inclusive": known,
                                  "upper_inclusive": known if unknown == 0 else None}}


def gate(*, baseline_quality, candidate_quality, minimum_relative_saving,
         maximum_quality_loss, baseline_cost=None, candidate_cost=None,
         costs_complete=False, matched_task_denominators=False,
         quality_loss_upper=None, savings_lower=None):
    """Point check and separate conservative evidence gate.

    Cost arguments must use the SAME denominator and scope (all attempts,
    including judge). Confidence bounds are optional, externally supplied
    paired estimates; none are invented from aggregate fixture scores.
    """
    bq = number(baseline_quality, "baseline_quality")
    cq = number(candidate_quality, "candidate_quality")
    limit = number(maximum_quality_loss, "maximum_quality_loss")
    saving_limit = number(minimum_relative_saving, "minimum_relative_saving")
    if any(v > 1 for v in (bq, cq, limit, saving_limit)):
        raise ValueError("quality and relative thresholds must be within [0, 1]")
    loss = bq - cq
    savings = None
    if costs_complete and matched_task_denominators and baseline_cost is not None and candidate_cost is not None:
        bc = number(baseline_cost, "baseline_cost")
        cc = number(candidate_cost, "candidate_cost")
        if bc <= 0:
            raise ValueError("relative savings requires positive baseline cost")
        savings = (bc - cc) / bc
    quality_pass = loss <= limit
    savings_pass = None if savings is None else savings >= saving_limit
    if not quality_pass or savings_pass is False:
        point_verdict = "reject"
    elif savings_pass is True:
        point_verdict = "pass"
    else:
        point_verdict = "indeterminate"
    bounds = (quality_loss_upper is not None and savings_lower is not None)
    bounds_pass = None
    if bounds:
        upper = Decimal(str(quality_loss_upper))
        lower = Decimal(str(savings_lower))
        if not upper.is_finite() or not lower.is_finite():
            raise ValueError("confidence bounds must be finite")
        bounds_pass = upper <= limit and lower >= saving_limit
    promotion = ("reject" if point_verdict == "reject" else
                 "eligible" if point_verdict == "pass" and bounds_pass else
                 "insufficient_evidence")
    return {"absolute_quality_loss": loss,
            "quality_point_gate": quality_pass,
            "relative_saving": savings,
            "saving_point_gate": savings_pass,
            "point_verdict": point_verdict,
            "confidence_bounds_pass": bounds_pass,
            "promotion": promotion}


def analyze(task):
    f = task["fixture"]
    baseline = ledger(f["attempts"], f["rates_usd_per_million"])
    sensitivity = []
    for inc_cache, inc_reason in ((True, True), (True, False), (False, True), (False, False)):
        result = ledger(f["attempts"], f["rates_usd_per_million"],
            input_includes_cache=inc_cache, output_includes_reasoning=inc_reason)
        sensitivity.append({"input_includes_cache": inc_cache,
            "output_includes_reasoning": inc_reason,
            "known_cost_usd": result["known_cost_usd"],
            "unknown_attempts": result["unknown_attempts"]})
    decision = gate(baseline_quality=f["baseline_quality"],
        candidate_quality=f["candidate_quality"],
        minimum_relative_saving=f["minimum_relative_saving"],
        maximum_quality_loss=f["maximum_quality_loss"])
    return {"task_id": task["id"], "evidence": "local fixed fixture; no live model measurement",
        "policy": {"input_includes_cache": True, "output_includes_reasoning": True,
                   "reported_cost_overrides_usage": True,
                   "unknown_is_zero": False},
        "rates_source": "task.json.fixture.rates_usd_per_million",
        "baseline": baseline, "candidate_cost_usd": None,
        "cost_per_completed_task_usd": None,
        "denominator_note": "No task IDs, task count, or task completion labels supplied; attempt status is not task success.",
        "decision": decision, "token_semantics_sensitivity": sensitivity,
        "minimum_quality": number(f["baseline_quality"], "quality") - number(f["maximum_quality_loss"], "loss"),
        "conditional_zero_unknown_cost_candidate_ceiling_usd":
            baseline["known_cost_usd"] * (1 - number(f["minimum_relative_saving"], "saving")),
        "conditional_ceiling_note": "Arithmetic scenario only: assumes missing baseline charge is zero and matched task counts. Not an observed saving."}


def serialize(value):
    if isinstance(value, Decimal):
        return format(value, "f")
    raise TypeError(type(value).__name__)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=Path("task.json"))
    parser.add_argument("--output", type=Path, default=Path("results.json"))
    args = parser.parse_args()
    raw = args.task.read_bytes()
    result = analyze(json.loads(raw, parse_float=Decimal))
    result["task_sha256"] = hashlib.sha256(raw).hexdigest()
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2,
                                      default=serialize) + "\n", encoding="utf-8")
    print(f"known_cost_usd={result['baseline']['known_cost_usd']}; "
          f"unknown_attempts={result['baseline']['unknown_attempts']}; "
          f"promotion={result['decision']['promotion']}")


if __name__ == "__main__":
    main()

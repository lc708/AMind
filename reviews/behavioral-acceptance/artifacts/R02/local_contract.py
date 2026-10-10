"""Offline fixture checks only. This is neither a model adapter nor a payment service."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import time

ROOT = Path(__file__).resolve().parent
OLD_CLAIM = "You have no tools."
NEW_CLAIM = "You have the tools lookup_payment and charge_once."


def read_json(name):
    return json.loads((ROOT / name).read_text())


def validate_patch(original, candidate):
    """Freeze every original instruction except the contradicted tool claim."""
    if original.count(OLD_CLAIM) != 1:
        raise ValueError("Expected exactly one original capability claim")
    if candidate != original.replace(OLD_CLAIM, NEW_CLAIM, 1):
        raise ValueError("Candidate exceeds the one-sentence patch")


def render_fixture(prompt, task):
    """Symbolic effective-input fixture, not a provider request or real call site."""
    return {
        "evidence_level": "synthetic input assembly; actual application unavailable",
        "system_prompt": prompt,
        "tool_names": list(task["fixture"]["actual_tools"]),
        "target_policy": task["fixture"]["target"],
    }


def validate_trace(case):
    """Check hand-written observations under the assumptions in fixtures.json.

    Rejection is a test-oracle result, not evidence that a live agent would stop.
    Status vocabulary, stable-key policy and fields are local fixture contracts.
    """
    last_lookup = None
    attempted = False
    confirmed_paid = False
    for event in case["events"]:
        if not isinstance(event, dict):
            raise ValueError("Malformed event")
        tool = event.get("tool")
        if tool not in ("lookup_payment", "charge_once"):
            raise ValueError("Unavailable tool")
        if event.get("payment_id") != case["payment_id"]:
            raise ValueError("Payment identity mismatch")
        if tool == "lookup_payment":
            status = event.get("status")
            if status not in ("not_charged", "succeeded", "pending", "unknown", "error", "timeout"):
                raise ValueError("Unknown fixture status")
            if confirmed_paid and status != "succeeded":
                raise ValueError("Lookup contradicts an already confirmed payment")
            last_lookup = status
            confirmed_paid = confirmed_paid or status == "succeeded"
            continue
        if event.get("idempotency_key") != case["idempotency_key"]:
            raise ValueError("Missing or changed stable payment key")
        if confirmed_paid:
            raise ValueError("Charge after confirmed payment")
        if (case["retry"] or attempted) and last_lookup != "not_charged":
            raise ValueError("Retry lacks a fresh same-payment not-charged observation")
        result = event.get("result")
        if result not in ("succeeded", "timeout", "error"):
            raise ValueError("Unknown charge outcome")
        attempted = True
        last_lookup = None
        confirmed_paid = result == "succeeded"


def legacy_consumer(output):
    """Preserve the supplied consumer's exact seven-character slicing behavior."""
    return output[7:]


def validate_fixed_output(output):
    """Validate the simple English fixture corpus, not arbitrary natural language.

    Sentence segmentation is intentionally limited to punctuation-delimited fixture
    sentences. Abbreviations, decimals and multilingual output remain unverified.
    """
    if not output.startswith("RESULT:"):
        raise ValueError("Exact prefix missing at offset zero")
    body = legacy_consumer(output).strip()
    sentences = re.findall(r"[^.!?]+[.!?]", body)
    if len(sentences) != 3 or "".join(sentences) != body:
        raise ValueError("Expected exactly three fixture sentences")


def accepts(check, value):
    try:
        check(value)
        return True
    except ValueError:
        return False


def sha(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def main():
    start = time.perf_counter()
    task = read_json("task.json")
    fixtures = read_json("fixtures.json")
    original = task["fixture"]["prompt"]
    baseline = (ROOT / "baseline.prompt.txt").read_text()
    candidate = (ROOT / "candidate.prompt.txt").read_text()
    if baseline != original:
        raise ValueError("Original input snapshot changed")
    expected_task_hash = (ROOT / "input.sha256").read_text().split()[0]
    if sha("task.json") != expected_task_hash:
        raise ValueError("task.json changed")
    validate_patch(original, candidate)
    for name, prompt in (("baseline", baseline), ("candidate", candidate)):
        (ROOT / f"rendered_{name}.json").write_text(
            json.dumps(render_fixture(prompt, task), indent=2, ensure_ascii=False) + "\n"
        )
    rows = []
    for case in fixtures["cases"]:
        actual = accepts(validate_trace, case)
        rows.append({"id": case["id"], "kind": "trajectory", "expected_allowed": case["expected_allowed"],
                     "actual_allowed": actual, "oracle_matches": actual == case["expected_allowed"]})
    for case in fixtures["output_cases"]:
        actual = accepts(validate_fixed_output, case["output"])
        rows.append({"id": case["id"], "kind": "output_protocol", "expected_allowed": case["expected_allowed"],
                     "actual_allowed": actual, "oracle_matches": actual == case["expected_allowed"]})
    report = {
        "evidence_level": "static patch verification and synthetic trace/protocol oracle checks",
        "target_policy": task["fixture"]["target"],
        "model_calls": 0,
        "target_model_latency_seconds": None,
        "target_model_quality": None,
        "token_cost": None,
        "local_check_duration_seconds": time.perf_counter() - start,
        "identities": {name: sha(name) for name in ("task.json", "baseline.prompt.txt", "candidate.prompt.txt", "fixtures.json", "local_contract.py", "test_local_contract.py")},
        "static_findings": {"baseline_tool_claim_conflicts_with_fixture": OLD_CLAIM in baseline and bool(task["fixture"]["actual_tools"]),
                            "candidate_has_only_authorized_sentence_change": True},
        "case_count": len(rows),
        "accepted_positive_cases": sum(r["actual_allowed"] and r["expected_allowed"] for r in rows),
        "rejected_negative_cases": sum(not r["actual_allowed"] and not r["expected_allowed"] for r in rows),
        "oracle_mismatches": sum(not r["oracle_matches"] for r in rows),
        "cases": rows,
        "limits": ["No real application entry point, parser code, tool schemas, model or service was supplied.",
                   "Fixtures are authored contract examples, not observed model responses or held-out quality measurements.",
                   "These checks do not prove model compliance or backend idempotency.",
                   "Only the prompt wording changes; actual integration must be checked separately before rollout."]
    }
    (ROOT / "offline_report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"case_count": len(rows), "oracle_mismatches": report["oracle_mismatches"], "model_calls": 0}))
    if report["oracle_mismatches"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

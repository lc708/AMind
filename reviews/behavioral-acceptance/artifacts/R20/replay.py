"""Run the supplied fixture offline and save reproducible structural evidence."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

from state import (ResponseChain, StateError, diagnose, fingerprint,
                   result_from_call)


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def replay(task_path, out, audit_script):
    task = json.loads(task_path.read_text(encoding="utf-8"))
    original_hash = fingerprint(task)
    fixture = task["fixture"]
    previous = fixture["previous_response"]
    original = fixture["next_request"]
    # No event provenance is supplied for this user message. Preserve it;
    # applications must instead source fresh input from their trusted event log.
    retained_users = [x for x in original["input"] if x.get("role") == "user"]
    old_results = [x for x in original["input"] if x.get("type") == "function_call_output"]
    state = ResponseChain(previous, "fixture:tenant-a:resource-a")
    try:
        state.prepare(retained_users, old_results, scope="fixture:tenant-a:resource-a")
    except StateError as exc:
        rejected = exc.code
    else:
        raise AssertionError("Broken fixture unexpectedly accepted")
    # Local dispatcher mock: exact supplied read call, fixed supplied output.
    # Do NOT relabel the untrusted 'wrong' result. Independently bind a mock
    # completion to the dispatcher-held call c1. No read tool is executed.
    call = next(x for x in previous["output"] if x.get("type") == "function_call")
    assert (call["name"], call["arguments"], call["call_id"]) == ("read", "{}", "c1")
    fixed_mock_output = "invoice"
    fixed = state.prepare(retained_users, [result_from_call(call, fixed_mock_output)],
                          scope="fixture:tenant-a:resource-a")
    before = diagnose(previous, original)
    after = diagnose(previous, fixed)
    assert before and not after
    assert fingerprint(task) == original_hash
    assert state.response == previous
    restored = ResponseChain.restore(json.loads(json.dumps(state.snapshot())),
                                     scope="fixture:tenant-a:resource-a")
    assert restored.snapshot() == state.snapshot()
    # The task contains one opaque item, not a complete compact response. Retain
    # it byte-for-byte as a JSON string value, but do not splice it into r1.
    opaque = fixture["later_compaction"]
    assert json.loads(json.dumps(opaque)) == opaque
    out.mkdir(parents=True, exist_ok=True)
    write(out / "original-fixture.json", fixture)
    write(out / "fixed-request.json", fixed)
    write(out / "state-snapshot.json", state.snapshot())
    write(out / "saved-compaction-item.json", opaque)
    start = {"state_owner": "response_chain", "request": {"input": []}, "response": previous}
    baseline = [start, {"state_owner": "response_chain", "request": original, "terminal": True}]
    corrected = [start, {"state_owner": "response_chain", "request": fixed, "terminal": True}]
    for name, turns in (("baseline", baseline), ("fixed", corrected)):
        (out / (name + ".jsonl")).write_text(
            "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in turns), encoding="utf-8")
    spec = importlib.util.spec_from_file_location("context_audit", audit_script)
    module = importlib.util.module_from_spec(spec)
    previous_bytecode_setting = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous_bytecode_setting
    baseline_audit, fixed_audit = module.audit(baseline), module.audit(corrected)
    assert baseline_audit["errors"] > 0 and fixed_audit["findings"] == []
    write(out / "baseline-audit.json", baseline_audit)
    write(out / "fixed-audit.json", fixed_audit)
    expected_replay = previous["output"][0]
    actual_replay = next(x for x in original["input"] if x.get("role") == "assistant")
    phase_diff = module.differences(expected_replay, actual_replay)
    write(out / "phase-diff.json", phase_diff)
    result = {"evidence_level": "offline fixed fixtures; no provider or model calls",
              "baseline_findings": before, "fixed_findings": after,
              "broken_result_rejected_as": rejected,
              "original_task_hash": original_hash, "compaction_hash": fingerprint(opaque),
              "preserved_input": "user message retained; history/new-event provenance absent",
              "tool_result_provenance": "fixed mock completion bound to original call c1",
              "compaction_limit": "single item archived; actual compact-output continuation unverified",
              "normalization": "unknown initial request represented as []; terminal marks local result check, not model success"}
    write(out / "diagnosis.json", result)
    print(json.dumps({"baseline_codes": [x["code"] for x in before], "fixed_findings": after,
                      "baseline_audit_errors": baseline_audit["errors"],
                      "fixed_audit_errors": fixed_audit["errors"],
                      "original_unchanged": fingerprint(json.loads(task_path.read_text())) == original_hash,
                      "output_directory": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task", type=Path, default=Path("task.json"))
    parser.add_argument("--out", type=Path, default=Path("artifacts"))
    parser.add_argument("--audit-script", type=Path, required=True)
    args = parser.parse_args()
    replay(args.task, args.out, args.audit_script)

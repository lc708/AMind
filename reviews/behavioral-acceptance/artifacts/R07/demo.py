"""Deterministic local demonstration; the second response is an explicit mock."""
from pathlib import Path
import json
from integration import parse_response, parse_tool_arguments, prepare_continuation, checkpoint, restore_checkpoint


def main():
    task = json.loads(Path(__file__).with_name("task.json").read_text())
    good = task["fixture"]["response_fixture"]
    bad = task["fixture"]["failure_fixture"]
    baseline = {}
    for name, response in (("response_fixture", good), ("failure_fixture", bad)):
        try:
            baseline[name] = response["output"][0]["content"][0]["text"]
        except (KeyError, IndexError) as error:
            baseline[name] = f"{type(error).__name__}: {error}"
    original_input = [{"role": "system", "content": "\n".join(task["constraints"])},
                      {"role": "user", "content": task["request"]}]
    saved = checkpoint(original_input, good, "fixture-turn-1")
    restored = restore_checkpoint(saved)
    parsed = parse_response(restored["response"])
    calls = []
    for call in parsed.tool_calls:
        if call["name"] != "lookup":
            raise ValueError("unknown local mock tool")
        args = parse_tool_arguments(call, lambda value: value == {})
        calls.append({"type": "function_call_output", "call_id": call["call_id"],
                      "output": json.dumps({"source": "fixed-local-mock", "value": "fixture-value"})})
    next_input = prepare_continuation(restored["history_before_response"], restored["response"], calls)
    # Fixed mock response, never claimed to have come from a model.
    final = parse_response({"status": "completed", "output": [{"type": "message", "role": "assistant", "phase": "final_answer", "content": [{"type": "output_text", "text": "Found fixture-value."}]}]})
    failure = parse_response(bad)
    evidence = {"evidence_type": "offline fixed fixtures, no API calls", "baseline": baseline,
                "response_fixture": {"state": parsed.state, "progress_text": parsed.progress_text,
                                     "final_text": parsed.final_text, "pending_call_ids": [c["call_id"] for c in parsed.tool_calls]},
                "continuation_input": next_input,
                "checkpoint_roundtrip_equal": restored["response"] == good,
                "mock_final": {"state": final.state, "final_text": final.final_text},
                "failure_fixture": {"state": failure.state, "final_text": failure.final_text,
                                    "usage": failure.usage, "diagnostics": failure.diagnostics}}
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

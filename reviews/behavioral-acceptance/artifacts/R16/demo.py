"""Public offline entry point; all service and lookup outcomes are fixed mocks."""
from pathlib import Path
import json

from integration import Session, call_arguments, parse_response
import legacy


ROOT = Path(__file__).resolve().parent


def message(text, phase="final_answer"):
    return {"type": "message", "role": "assistant", "phase": phase,
            "content": [{"type": "output_text", "text": text}]}


def run_demo():
    task = json.loads((ROOT / "task.json").read_text())
    fixture = task["fixture"]
    config = {"instructions": "offline fixed fixture; preserve task behavior",
              "max_output_tokens": 100}
    initial = [{"role": "user", "content": "Run the fixed local lookup fixture."}]
    session = Session(scope="fixture:G02", config=config, history=initial)
    first_request = session.request()
    first = session.accept(fixture["response_fixture"], delivery_id="turn-1")
    # Simulate process shutdown and reconnect before consuming pending tool calls.
    session = Session.restore(json.loads(json.dumps(session.snapshot())),
                              expected_scope="fixture:G02")
    for call in session.pending_calls:
        if call["name"] != "lookup" or call_arguments(call) != {}:
            raise ValueError("only the exact fixed lookup mock is available")
        result = {"ok": True, "value": "fixed-lookup-result", "source": "local mock"}
        session.record_tool_result(call["call_id"], json.dumps(result, sort_keys=True))
    continuation = session.request()
    # This final response is invented fixed test data, not a target-model answer.
    final_response = {"status": "completed", "output": [message("Lookup complete.")]}
    final = session.accept(final_response, delivery_id="turn-2")
    failure_session = Session(scope="fixture:G02:failure", config=config, history=initial)
    failure = failure_session.accept(fixture["failure_fixture"], delivery_id="failure-1")
    try:
        baseline = {"text": legacy.parse(fixture["response_fixture"])}
    except (KeyError, IndexError) as exc:
        baseline = {"exception": type(exc).__name__, "detail": str(exc)}
    trace = [
        {"state_owner": "client", "request": first_request,
         "response": fixture["response_fixture"]},
        {"state_owner": "client", "request": continuation,
         "response": final_response, "terminal": True},
    ]
    result = {"evidence": "offline fixed fixtures only; no model or network calls",
              "baseline": baseline, "first": first, "continuation_request": continuation,
              "final": final, "failure": failure,
              "failure_snapshot": failure_session.snapshot(),
              "snapshot": session.snapshot()}
    return result, trace


if __name__ == "__main__":
    result, trace = run_demo()
    (ROOT / "demo-output.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    (ROOT / "continuation-trace.jsonl").write_text(
        "".join(json.dumps(turn, ensure_ascii=False) + "\n" for turn in trace))
    print(json.dumps({"initial_outcome": result["first"]["outcome"],
                      "display_text": result["first"]["display_text"],
                      "final_outcome": result["final"]["outcome"],
                      "failure_outcome": result["failure"]["outcome"],
                      "failure_usage": result["failure"]["usage"]}, ensure_ascii=False))

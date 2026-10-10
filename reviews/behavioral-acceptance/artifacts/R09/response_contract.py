"""Offline Responses stream and batch contracts; Python standard library only.

Adapted from the assigned AMind Engineering response_contract.py reference.
Success here means completed transport, not correctness of generated content.
"""

import argparse
import copy
import json
from collections import Counter
from pathlib import Path


class ContractError(ValueError):
    """Malformed or ambiguous input cannot be reported as success."""


def _object(value, label):
    if not isinstance(value, dict):
        raise ContractError(label + " must be an object")
    return value


def normalize_response(response):
    """Keep the full response while providing explicit outcome projections."""
    _object(response, "response")
    output = response.get("output", [])
    if not isinstance(output, list):
        raise ContractError("response.output must be an array")
    text, refusals, calls = [], [], []
    for item in output:
        _object(item, "output item")
        if item.get("type") == "function_call":
            calls.append(copy.deepcopy(item))
        if item.get("type") != "message":
            continue
        content = item.get("content", [])
        if not isinstance(content, list):
            raise ContractError("message.content must be an array")
        for part in content:
            _object(part, "content item")
            field = {"output_text": "text", "refusal": "refusal"}.get(part.get("type"))
            if field is not None:
                value = part.get(field)
                if not isinstance(value, str):
                    raise ContractError(field + " must be a string")
                (text if field == "text" else refusals).append(value)
    status = response.get("status", "unknown")
    if not isinstance(status, str):
        raise ContractError("response.status must be a string")
    if status == "completed" and response.get("error") is not None:
        raise ContractError("completed response contains an error")
    return {
        "status": status,
        "transport_success": status == "completed",
        "text": "".join(text),
        "refusals": refusals,
        "function_calls": calls,
        "usage": copy.deepcopy(response.get("usage")),
        "incomplete_details": copy.deepcopy(response.get("incomplete_details")),
        "error": copy.deepcopy(response.get("error")),
        "raw_response": copy.deepcopy(response),
    }


def terminal_stream(events):
    """Deltas are provisional; only a matching completed event is success.

    This consumes already-decoded finite events. A caller that catches a live
    read/timeout failure must finish this iterable or emit an error event; it
    must not synthesize a completed event. Malformed traces raise ContractError.
    """
    terminal, stream_error = None, None
    deltas, raw_events = [], []
    terminal_types = {
        "response.completed": "completed",
        "response.failed": "failed",
        "response.incomplete": "incomplete",
    }
    for event in events:
        _object(event, "stream event")
        if terminal is not None or stream_error is not None:
            raise ContractError("event after terminal outcome")
        kind = event.get("type")
        if not isinstance(kind, str) or not kind:
            raise ContractError("stream event.type must be a nonempty string")
        raw_events.append(copy.deepcopy(event))
        if kind == "response.output_text.delta":
            delta = event.get("delta")
            if not isinstance(delta, str):
                raise ContractError("text delta must be a string")
            deltas.append(delta)
        elif kind in terminal_types:
            terminal = _object(event.get("response"), "terminal response")
            if terminal.get("status") != terminal_types[kind]:
                raise ContractError("terminal event/status mismatch")
        elif kind == "error":
            stream_error = copy.deepcopy(event)
        # Unknown nonterminal events are retained, never promoted to success.
    if terminal is not None:
        result = normalize_response(terminal)
    else:
        result = {
            "status": "stream_error" if stream_error is not None else "disconnected",
            "transport_success": False,
            "text": None,
            "refusals": [],
            "function_calls": [],
            "usage": None,
            "incomplete_details": None,
            "error": stream_error,
            "raw_response": None,
        }
    result["display_deltas"] = "".join(deltas)
    result["raw_events"] = raw_events
    return result


def _batch_row(row):
    """HTTP success alone is insufficient for a Responses batch row."""
    base = {"custom_id": row["custom_id"], "raw": copy.deepcopy(row)}
    if row.get("error") is not None:
        _object(row["error"], "batch error")
        return dict(base, status="batch_error", transport_success=False,
                    error=copy.deepcopy(row["error"]))
    response = _object(row.get("response"), "batch response")
    code = response.get("status_code")
    if type(code) is not int or not 100 <= code <= 599:
        raise ContractError("batch status_code must be an HTTP integer")
    if not 200 <= code < 300:
        return dict(base, status="http_error", transport_success=False,
                    status_code=code, error=copy.deepcopy(response.get("body")))
    normalized = normalize_response(response.get("body"))
    return dict(base, status=normalized["status"],
                transport_success=normalized["transport_success"],
                status_code=code, response=normalized)


def match_batch(request_ids, results):
    """Reconcile downloaded output AND error records by unique custom_id.

    Every requested ID receives exactly one ordered outcome. Unknown/duplicate
    IDs raise instead of overwriting or silently pairing unrelated requests.
    """
    if isinstance(request_ids, (str, bytes)):
        raise ContractError("request_ids must be a sequence of IDs")
    requested = list(request_ids)
    if any(not isinstance(key, str) or not key for key in requested):
        raise ContractError("request custom_id must be a nonempty string")
    expected = set(requested)
    if len(requested) != len(expected):
        raise ContractError("duplicate request custom_id")
    indexed = {}
    for row in results:
        _object(row, "batch row")
        key = row.get("custom_id")
        if not isinstance(key, str) or key not in expected:
            raise ContractError("unknown batch custom_id")
        if key in indexed:
            raise ContractError("duplicate batch custom_id")
        indexed[key] = _batch_row(row)
    ordered = [indexed.get(key, {"custom_id": key, "status": "missing",
                               "transport_success": False, "raw": None})
               for key in requested]
    return {
        "ordered": ordered,
        "missing": [row["custom_id"] for row in ordered if row["status"] == "missing"],
        "errors": [row["custom_id"] for row in ordered
                   if row["status"] != "missing" and not row["transport_success"]],
        "counts": dict(Counter(row["status"] for row in ordered)),
        "requested_count": len(requested),
        "returned_count": len(indexed),
        "all_transport_success": all(row["transport_success"] for row in ordered),
    }


def evaluate_fixture(task):
    fixture = task["fixture"]
    return {
        "task_id": task["id"],
        "evidence": "offline_fixed_fixture",
        "stream": terminal_stream(fixture["stream"]),
        "batch": match_batch(fixture["batch_requested"], fixture["batch_returned"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", type=Path, help="Unmodified local task.json")
    parser.add_argument("--output", type=Path, help="Optional report destination")
    args = parser.parse_args(argv)
    if args.output and args.output.resolve() == args.task.resolve():
        parser.error("output must not overwrite the input")
    try:
        report = evaluate_fixture(json.loads(args.task.read_text(encoding="utf-8")))
    except (ContractError, KeyError, TypeError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    serialized = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
    print(serialized, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

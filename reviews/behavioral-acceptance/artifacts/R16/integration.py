"""Offline JSON adapter. No SDK, credentials, networking or tool execution.

The application owns client replay. Unknown/opaque output fields are retained;
text and completion are projections, never substitutes for protocol state.
"""
from copy import deepcopy
import hashlib
import json


class ProtocolError(ValueError):
    pass


class ContinuationBlocked(ProtocolError):
    pass


def clone(value):
    # Check the actual serialization boundary, including rejecting NaN/Infinity.
    json.dumps(value, allow_nan=False)
    return deepcopy(value)


def fingerprint(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def parse_response(response):
    """Return a lossless response plus conservative, phase-aware UI projections."""
    if not isinstance(response, dict):
        raise ProtocolError("response must be an object")
    raw = clone(response)
    status, items = raw.get("status"), raw.get("output")
    if not isinstance(status, str) or not status:
        raise ProtocolError("response status is required")
    if not isinstance(items, list):
        raise ProtocolError("response output must be an array")
    display, final, commentary, refusals, calls = [], [], [], [], []
    for item in items:
        if not isinstance(item, dict):
            raise ProtocolError("each output item must be an object")
        if item.get("type") == "function_call":
            calls.append(clone(item))
        if item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            raise ProtocolError("message content must be an array")
        for part in content:
            if not isinstance(part, dict):
                raise ProtocolError("message content item must be an object")
            kind = part.get("type")
            if kind == "output_text":
                text = part.get("text")
                if not isinstance(text, str):
                    raise ProtocolError("output_text.text must be a string")
                display.append(text)
                if item.get("role") == "assistant":
                    phase = item.get("phase")
                    if phase is None or phase == "final_answer":
                        final.append(text)
                    elif phase == "commentary":
                        commentary.append(text)
            elif kind == "refusal":
                value = part.get("refusal")
                if not isinstance(value, str):
                    raise ProtocolError("refusal must be a string")
                refusals.append(value)
    if status != "completed":
        outcome = status if status in {"incomplete", "failed", "cancelled", "queued", "in_progress"} else "unknown_status"
    elif refusals:
        outcome = "refused"
    elif calls:
        outcome = "tool_required"
    elif final:
        outcome = "final"
    else:
        outcome = "awaiting_final"
    return {
        "raw_response": raw,
        "output_items": clone(items),
        "status": status,
        "outcome": outcome,
        "task_complete": status == "completed" and outcome == "final",
        "display_text": "".join(display),
        "commentary_text": "".join(commentary),
        "final_text": "".join(final) if status == "completed" and outcome == "final" else None,
        "refusals": refusals,
        "function_calls": calls,
        "usage": clone(raw.get("usage")),
        "incomplete_details": clone(raw.get("incomplete_details")),
        "error": clone(raw.get("error")),
    }


def call_arguments(call):
    for key in ("call_id", "name", "arguments"):
        if not isinstance(call.get(key), str) or not call[key]:
            raise ProtocolError("function_call requires nonempty " + key)
    try:
        arguments = json.loads(call["arguments"])
    except (ValueError, TypeError) as exc:
        raise ProtocolError("tool arguments must be valid JSON") from exc
    if not isinstance(arguments, dict):
        raise ProtocolError("tool arguments must be an object")
    clone(arguments)
    return arguments


def tool_ledger(history):
    """Validate correspondence before committing any history mutation."""
    calls, results = {}, {}
    for item in history:
        if not isinstance(item, dict):
            raise ProtocolError("history item must be an object")
        kind = item.get("type")
        if kind == "function_call":
            call_arguments(item)
            key = item["call_id"]
            if key in calls:
                raise ProtocolError("duplicate function call ID: " + key)
            calls[key] = item
        elif kind == "function_call_output":
            key = item.get("call_id")
            if not isinstance(key, str) or key not in calls:
                raise ProtocolError("orphan tool result")
            if key in results or not isinstance(item.get("output"), str):
                raise ProtocolError("duplicate or malformed tool result")
            results[key] = item
    return calls, results


class Session:
    """Client-owned replay state; caller supplies a trusted local resource scope.

    delivery_id is a stable application event ID, persisted with the snapshot.
    Re-delivering the same event is a no-op. No method invokes any tool or model.
    """

    def __init__(self, *, scope, config, history):
        if not isinstance(scope, str) or not scope:
            raise ProtocolError("a trusted scope is required")
        if not isinstance(config, dict):
            raise ProtocolError("config must be an object")
        if any(key in config for key in ("input", "previous_response_id", "conversation")):
            raise ProtocolError("client replay cannot also use server-owned history")
        if not isinstance(history, list):
            raise ProtocolError("history must be an array")
        tool_ledger(history)
        self.scope = scope
        self._config, self._history = clone(config), clone(history)
        self._responses = {}
        self._blocked = None

    @property
    def history(self):
        return clone(self._history)

    @property
    def pending_calls(self):
        if self._blocked:
            raise ContinuationBlocked(self._blocked)
        calls, results = tool_ledger(self._history)
        return clone([call for key, call in calls.items() if key not in results])

    def request(self):
        if self._blocked:
            raise ContinuationBlocked(self._blocked)
        if self.pending_calls:
            raise ContinuationBlocked("tool results are still required")
        return {**clone(self._config), "input": self.history}

    def accept(self, response, *, delivery_id):
        if not isinstance(delivery_id, str) or not delivery_id:
            raise ProtocolError("stable delivery_id is required")
        parsed = parse_response(response)
        if delivery_id in self._responses:
            if fingerprint(self._responses[delivery_id]) != fingerprint(response):
                raise ProtocolError("delivery_id reused for a different response")
            return parsed
        if self._blocked:
            raise ContinuationBlocked(self._blocked)
        if self.pending_calls:
            raise ContinuationBlocked("cannot accept a response before tool results")
        # Failure payloads remain in the journal, but are never silently replayed.
        if parsed["status"] != "completed":
            self._responses[delivery_id] = clone(response)
            self._blocked = parsed["status"]
            return parsed
        next_history = self._history + parsed["output_items"]
        tool_ledger(next_history)
        if parsed["refusals"] and parsed["function_calls"]:
            raise ProtocolError("refusal with a tool call requires explicit policy")
        self._history = clone(next_history)
        self._responses[delivery_id] = clone(response)
        return parsed

    def record_tool_result(self, call_id, output):
        if self._blocked:
            raise ContinuationBlocked(self._blocked)
        calls, results = tool_ledger(self._history)
        if not isinstance(call_id, str) or call_id not in calls:
            raise ProtocolError("unknown call_id")
        if not isinstance(output, str):
            raise ProtocolError("tool output must be an explicitly serialized string")
        if call_id in results:
            if results[call_id]["output"] != output:
                raise ProtocolError("conflicting duplicate tool result")
            return False
        self._history.append({"type": "function_call_output", "call_id": call_id,
                              "output": output})
        return True

    def append_input(self, items):
        self.request()  # Reject cancellation, failed state or unresolved tools.
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or item.get("role") != "user"
            or item.get("type", "message") != "message" for item in items
        ):
            raise ProtocolError("new input must be user item objects")
        self._history.extend(clone(items))

    def cancel(self):
        self._blocked = "cancelled"

    def snapshot(self):
        return clone({"version": 1, "state_owner": "client", "scope": self.scope,
                      "config": self._config, "history": self._history,
                      "responses": self._responses, "blocked": self._blocked})

    @classmethod
    def restore(cls, snapshot, *, expected_scope):
        if not isinstance(snapshot, dict) or snapshot.get("version") != 1:
            raise ProtocolError("unsupported snapshot version")
        if snapshot.get("state_owner") != "client":
            raise ProtocolError("snapshot has a different state owner")
        if snapshot.get("scope") != expected_scope:
            raise ProtocolError("snapshot scope mismatch")
        session = cls(scope=expected_scope, config=snapshot["config"],
                      history=snapshot["history"])
        responses = snapshot.get("responses")
        if not isinstance(responses, dict):
            raise ProtocolError("snapshot response journal must be an object")
        for key, raw in responses.items():
            if not isinstance(key, str) or not key:
                raise ProtocolError("invalid snapshot delivery_id")
            parse_response(raw)
        blocked = snapshot.get("blocked")
        if blocked is not None and (not isinstance(blocked, str) or not blocked):
            raise ProtocolError("invalid snapshot blocked state")
        session._responses, session._blocked = clone(responses), blocked
        return session

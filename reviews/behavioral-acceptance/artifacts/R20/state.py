"""Offline continuation boundary; standard library only, no transport or tools.

ResponseChain owns response-ID continuation. The host supplies authenticated
scope and explicit new user items; model output is never reinterpreted as input.
"""
import copy
import hashlib
import json


class StateError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def clone(value):
    # Verify that the complete stored value can cross the JSON boundary.
    json.dumps(value, allow_nan=False)
    return copy.deepcopy(value)


def check_items(items):
    if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
        raise StateError("items_must_be_object_array")


def check_user_input(items):
    check_items(items)
    for item in items:
        if item.get("role") != "user" or item.get("type", "message") != "message":
            raise StateError("fresh_input_must_be_user_message")
        if "content" not in item:
            raise StateError("missing_user_content")


def check_settings(settings):
    if not isinstance(settings, dict):
        raise StateError("settings_must_be_object")
    if {"input", "previous_response_id", "conversation"} & settings.keys():
        raise StateError("mixed_state_owners")


def pending_calls(response):
    check_items(response.get("output"))
    calls = {}
    for item in response["output"]:
        if item.get("type") != "function_call":
            continue
        key = item.get("call_id")
        if not isinstance(key, str) or not key:
            raise StateError("missing_call_id")
        if key in calls:
            raise StateError("duplicate_call_id")
        if not isinstance(item.get("name"), str) or not item["name"]:
            raise StateError("missing_tool_name")
        try:
            args = item.get("arguments")
            if not isinstance(args, str) or not isinstance(json.loads(args), dict):
                raise ValueError()
        except (ValueError, TypeError):
            raise StateError("malformed_arguments")
        calls[key] = item
    return calls


def result_from_call(call, output):
    """Use the dispatcher-held call identity; never repair a guessed result ID."""
    if call.get("type") != "function_call" or not isinstance(call.get("call_id"), str):
        raise StateError("invalid_dispatch_call")
    if not isinstance(output, str):
        raise StateError("tool_output_must_be_string")
    return {"type": "function_call_output", "call_id": call["call_id"], "output": output}


class ResponseChain:
    def __init__(self, response, scope):
        if not isinstance(scope, str) or not scope:
            raise StateError("missing_scope")
        if not isinstance(response, dict) or not isinstance(response.get("id"), str) or not response["id"]:
            raise StateError("missing_response_id")
        pending_calls(response)
        self._response = clone(response)
        self._scope = scope
        self._cancelled = False
        self._prepared = None
        self._seen_responses = [response["id"]]
        self._seen_calls = list(pending_calls(response))

    def _check_scope(self, scope):
        if scope != self._scope:
            raise StateError("scope_mismatch")

    @property
    def response(self):
        return clone(self._response)

    def prepare(self, new_input, results, *, scope, settings=None):
        """Prepare without sending; same-parent retries must be structurally identical.

        This boundary waits for every pending call. Partial parallel results are
        deliberately unsupported. No dispatch or external idempotency is implied.
        """
        self._check_scope(scope)
        if self._cancelled:
            raise StateError("cancelled")
        status = self._response.get("status")
        if status is not None and status != "completed":
            raise StateError("response_not_completed")
        check_user_input(new_input)
        check_items(results)
        settings = {} if settings is None else settings
        check_settings(settings)
        calls = pending_calls(self._response)
        seen = set()
        for result in results:
            if result.get("type") != "function_call_output":
                raise StateError("malformed_tool_result")
            key = result.get("call_id")
            if not isinstance(key, str) or key not in calls:
                raise StateError("orphan_tool_result")
            if key in seen:
                raise StateError("duplicate_tool_result")
            if not isinstance(result.get("output"), str):
                raise StateError("tool_output_must_be_string")
            seen.add(key)
        if seen != set(calls):
            raise StateError("unresolved_tool_calls")
        request = clone(settings)
        request.update(previous_response_id=self._response["id"],
                       input=clone(new_input + results))
        if self._prepared is not None and request != self._prepared:
            raise StateError("inflight_request_changed")
        self._prepared = clone(request)
        return request

    def accept(self, request, response, *, scope):
        """Advance only upon an observed successor to our exact prepared request."""
        self._check_scope(scope)
        if self._cancelled:
            raise StateError("cancelled")
        if self._prepared is None or request != self._prepared:
            raise StateError("unrecognized_request")
        candidate = ResponseChain(response, scope)
        if response["id"] in self._seen_responses:
            raise StateError("duplicate_response_id")
        calls = pending_calls(response)
        if set(calls) & set(self._seen_calls):
            raise StateError("reused_call_id")
        self._response = candidate.response
        self._seen_responses.append(response["id"])
        self._seen_calls.extend(calls)
        self._prepared = None

    def cancel(self):
        self._cancelled = True

    def snapshot(self):
        return clone({"version": 1, "state_owner": "response_chain", "scope": self._scope,
                      "response": self._response, "cancelled": self._cancelled,
                      "prepared": self._prepared, "seen_responses": self._seen_responses,
                      "seen_calls": self._seen_calls})

    @classmethod
    def restore(cls, snapshot, *, scope):
        # Trusted application storage, not a model-supplied or authenticated blob.
        if snapshot.get("version") != 1 or snapshot.get("state_owner") != "response_chain":
            raise StateError("unsupported_snapshot")
        if snapshot.get("scope") != scope:
            raise StateError("scope_mismatch")
        restored = cls(snapshot["response"], scope)
        restored._cancelled = snapshot["cancelled"]
        restored._prepared = clone(snapshot["prepared"])
        restored._seen_responses = clone(snapshot["seen_responses"])
        restored._seen_calls = clone(snapshot["seen_calls"])
        return restored


def final_messages(response):
    """Missing status or commentary is never evidence of a final answer."""
    if response.get("status") != "completed" or pending_calls(response):
        return []
    return clone([item for item in response["output"]
                  if item.get("type") == "message" and item.get("role") == "assistant"
                  and item.get("phase") == "final_answer"])


def client_compaction_request(compact_output, new_input, *, expected_hash,
                              source_scope, scope, settings=None):
    """Separate client-owned boundary, only for an actual complete compact output.

    The caller must establish provider compatibility and scope. This function
    cannot recover the full compact output from a lone encrypted item.
    """
    if source_scope != scope:
        raise StateError("scope_mismatch")
    check_items(compact_output)
    if fingerprint(compact_output) != expected_hash:
        raise StateError("changed_compaction")
    if not any(x.get("type") == "compaction" and isinstance(x.get("encrypted_content"), str)
               and x["encrypted_content"] for x in compact_output):
        raise StateError("missing_compaction")
    check_user_input(new_input)
    settings = {} if settings is None else settings
    check_settings(settings)
    return dict(clone(settings), input=clone(compact_output + new_input))


def diagnose(previous, request):
    """Fixture-level diagnostics; similarities identify candidates, never dedup."""
    found = []
    if request.get("previous_response_id") != previous.get("id"):
        found.append({"code": "wrong_parent", "path": "/next_request/previous_response_id"})
    if request.get("conversation") is not None:
        found.append({"code": "mixed_state_owners", "path": "/next_request/conversation"})
    known = pending_calls(previous)
    resolved = set()
    for index, item in enumerate(request.get("input", [])):
        path = "/next_request/input/" + str(index)
        if item.get("role") == "assistant":
            found.append({"code": "assistant_in_chain_input", "path": path})
            for old in previous["output"]:
                if (old.get("role") == "assistant" and old.get("content") == item.get("content")
                        and old.get("phase") is not None and old.get("phase") != item.get("phase")):
                    found.append({"code": "phase_drift", "path": path + "/phase"})
        if item.get("type") == "function_call_output":
            key = item.get("call_id")
            if key not in known:
                found.append({"code": "orphan_tool_result", "path": path + "/call_id"})
            elif key in resolved:
                found.append({"code": "duplicate_tool_result", "path": path + "/call_id"})
            else:
                resolved.add(key)
    if set(known) - resolved:
        found.append({"code": "unresolved_tool_calls", "path": "/previous_response/output",
                      "call_ids": sorted(set(known) - resolved)})
    return found

"""Offline adapter for task.json's response format; no SDK or network calls.

Raw replay state and product display state are deliberately separate. Only the
caller may execute tools; this module validates and links supplied tool results.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import json


class ProtocolError(ValueError):
    """Malformed data or an unsafe continuation request."""


@dataclass(frozen=True)
class ParsedResponse:
    state: str
    progress_text: str
    final_text: str | None
    tool_calls: tuple
    raw: dict
    diagnostics: tuple

    @property
    def usage(self):
        return deepcopy(self.raw.get("usage", {}))


def _object(value, path):
    if not isinstance(value, dict):
        raise ProtocolError(f"{path} must be an object")
    return value


def _string(value, path):
    if not isinstance(value, str):
        raise ProtocolError(f"{path} must be a string")
    return value


def parse_response(response):
    """Inspect types, never assume output[0] is a user-visible message.

    Missing phase is supported for legacy final messages. Explicit commentary
    never becomes a final answer. Unknown types remain in raw replay state and
    block automatic completion/execution until a caller supports them.
    """
    raw = deepcopy(_object(response, "response"))
    output = raw.get("output")
    if not isinstance(output, list):
        raise ProtocolError("response.output must be an array")
    progress, answers, calls, diagnostics, refusals = [], [], [], [], []
    call_ids = set()
    unsupported = False
    for i, value in enumerate(output):
        item = _object(value, f"output[{i}]")
        kind = _string(item.get("type"), f"output[{i}].type")
        if kind == "reasoning":
            # Opaque state is neither interpreted nor rendered.
            continue
        if kind == "function_call":
            call_id = _string(item.get("call_id"), "function_call.call_id")
            name = _string(item.get("name"), "function_call.name")
            _string(item.get("arguments"), "function_call.arguments")
            if not call_id or not name or call_id in call_ids:
                raise ProtocolError("empty name/id or duplicate function call id")
            call_ids.add(call_id)
            calls.append(deepcopy(item))
            continue
        if kind != "message":
            unsupported = True
            diagnostics.append(f"unsupported output type: {kind}")
            continue
        if item.get("role") != "assistant":
            unsupported = True
            diagnostics.append("unsupported output message role")
            continue
        phase = item.get("phase")
        if phase not in (None, "commentary", "final_answer"):
            unsupported = True
            diagnostics.append(f"unsupported message phase: {phase}")
        content = item.get("content")
        if not isinstance(content, list):
            raise ProtocolError("message.content must be an array")
        parts = []
        for j, block in enumerate(content):
            _object(block, f"message.content[{j}]")
            if block.get("type") == "output_text":
                parts.append(_string(block.get("text"), "output_text.text"))
            elif block.get("type") == "refusal":
                refusals.append(_string(block.get("refusal"), "refusal.refusal"))
            else:
                unsupported = True
                diagnostics.append(f"unsupported content type: {block.get('type')}")
        text = "".join(parts)
        if phase == "commentary":
            progress.append(text)
        elif phase in (None, "final_answer"):
            answers.append(text)
    status = raw.get("status")
    final = None
    if status == "incomplete":
        detail = raw.get("incomplete_details") or {}
        _object(detail, "incomplete_details")
        reason = detail.get("reason", "unknown")
        state = "incomplete"
        diagnostics.append(f"incomplete: {reason}")
        if reason == "max_output_tokens":
            diagnostics.append("retry original request only with an explicit larger budget; do not execute this turn's tools")
    elif status in ("failed", "cancelled"):
        state = status
        diagnostics.append(f"response {status}")
    elif status in ("queued", "in_progress"):
        state = "pending"
    elif status != "completed":
        state = "unsupported"
        diagnostics.append(f"unsupported response status: {status}")
    elif refusals:
        state = "refused"
        diagnostics.append("response contains refusal")
    elif unsupported:
        state = "unsupported"
    elif calls:
        state = "needs_tools"
    elif any(answers):
        state, final = "final", "\n".join(answers)
    else:
        state = "needs_continuation"
        diagnostics.append("completed transport response has no final answer")
    return ParsedResponse(state, "\n".join(progress), final, tuple(calls), raw, tuple(diagnostics))


def replay_history(history, response):
    """Copy all output items, in order, without reconstructing rendered text.

    This does not declare the response safe to continue. Failure envelopes must
    also be kept in application diagnostics, not inferred from this flat list.
    """
    if not isinstance(history, list):
        raise ProtocolError("history must be an array")
    parsed = parse_response(response)
    return deepcopy(history) + deepcopy(parsed.raw["output"])


def parse_tool_arguments(call, validator):
    """Strict JSON parsing plus the actual tool's local schema validator.

    Never dispatch based on a tool name from the response alone. Select a known
    tool and its validator before invoking this helper. No tools run here.
    """
    def reject_constant(value):
        raise ProtocolError(f"non-JSON numeric constant: {value}")

    def unique_keys(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ProtocolError(f"duplicate argument key: {key}")
            result[key] = value
        return result

    _object(call, "call")
    try:
        arguments = json.loads(_string(call.get("arguments"), "arguments"),
                               parse_constant=reject_constant,
                               object_pairs_hook=unique_keys)
    except json.JSONDecodeError as error:
        raise ProtocolError("invalid or truncated tool arguments") from error
    _object(arguments, "arguments")
    if validator(deepcopy(arguments)) is not True:
        raise ProtocolError("tool arguments failed schema validation")
    return arguments


def prepare_continuation(history, response, tool_results=()):
    """Build one next-turn input; reject missing/duplicate/unrelated results.

    Results are supplied by the caller in the fixture's function_call_output
    form. Their matching call_id is checked and all results are appended after
    all original response items. Caller must commit this once per response.
    """
    parsed = parse_response(response)
    if parsed.state not in ("needs_tools", "needs_continuation"):
        raise ProtocolError(f"cannot auto-continue state: {parsed.state}")
    expected = {call["call_id"] for call in parsed.tool_calls}
    supplied = {}
    for result in tool_results:
        _object(result, "tool_result")
        if result.get("type") != "function_call_output":
            raise ProtocolError("tool result type must be function_call_output")
        call_id = _string(result.get("call_id"), "tool_result.call_id")
        _string(result.get("output"), "tool_result.output")
        if call_id not in expected or call_id in supplied:
            raise ProtocolError("unknown or duplicate tool result call_id")
        supplied[call_id] = deepcopy(result)
    if set(supplied) != expected:
        raise ProtocolError("every function call needs exactly one result")
    ordered_results = [supplied[call["call_id"]] for call in parsed.tool_calls]
    return replay_history(history, parsed.raw) + ordered_results


def checkpoint(history, response, turn_key):
    """JSON round-trip checkpoint, including envelope and opaque output state.

    turn_key is the caller's stable identity for this received response. The
    caller must deduplicate it before consuming twice; fixtures supply no ID.
    """
    if not isinstance(turn_key, str) or not turn_key:
        raise ProtocolError("a stable, nonempty turn_key is required")
    parsed = parse_response(response)
    if not isinstance(history, list):
        raise ProtocolError("history must be an array")
    return json.dumps({"version": 1, "turn_key": turn_key,
                       "history_before_response": history, "response": parsed.raw},
                      ensure_ascii=False, allow_nan=False)


def restore_checkpoint(serialized):
    data = json.loads(serialized)
    _object(data, "checkpoint")
    if data.get("version") != 1:
        raise ProtocolError("unsupported checkpoint version")
    # Reuse checkpoint validation, then copy away from serialized state.
    checkpoint(data.get("history_before_response"), data.get("response"), data.get("turn_key"))
    return deepcopy(data)

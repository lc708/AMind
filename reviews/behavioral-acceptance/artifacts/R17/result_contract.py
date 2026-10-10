"""Offline contracts for the exact decoded JSON shapes supplied in task.json.

No SDK, credentials, network, retries, or implicit provider-format conversion.
These are application outcomes, not replacements for SDK response types.
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from copy import deepcopy
from pathlib import Path
from typing import Any


TERMINALS = {
    "response.completed": ("completed", "succeeded"),
    "response.failed": ("failed", "failed"),
    "response.incomplete": ("incomplete", "incomplete"),
    "response.cancelled": ("cancelled", "cancelled"),
}


class StreamJudge:
    """Accumulate provisional text; only a coherent terminal event can succeed.

    feed() accepts decoded event dictionaries. finish() marks clean EOF without
    a terminal event incomplete. A terminal event must be the last event in this
    local contract; contradictory/trailing events are protocol errors.
    """

    def __init__(self) -> None:
        self._parts: list[str] = []
        self._status = "running"
        self._reason = "awaiting_terminal_event"
        self._terminal: str | None = None
        self._response: dict[str, Any] | None = None
        self._seen = 0
        self._closed = False

    def _invalid(self, reason: str) -> None:
        self._status, self._reason = "protocol_error", reason

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "success": self._status == "succeeded",
            "reason": self._reason,
            "partial_text": "".join(self._parts),
            "terminal_event": self._terminal,
            "events_seen": self._seen,
            "final_response": deepcopy(self._response),
        }

    def feed(self, event: Any) -> dict[str, Any]:
        if self._closed:
            raise RuntimeError("cannot feed after finish")
        self._seen += 1
        if self._status == "protocol_error":
            return self.snapshot()
        if self._terminal is not None:
            self._invalid("event_after_terminal")
            return self.snapshot()
        if not isinstance(event, dict) or not isinstance(event.get("type"), str):
            self._invalid("malformed_event")
            return self.snapshot()
        kind = event["type"]
        if kind == "response.output_text.delta":
            if not isinstance(event.get("delta"), str):
                self._invalid("malformed_text_delta")
            else:
                self._parts.append(event["delta"])
        elif kind == "error":
            self._terminal = kind
            self._status, self._reason = "failed", "stream_error_event"
            self._response = deepcopy(event)
        elif kind in TERMINALS:
            self._terminal = kind
            expected_status, outcome = TERMINALS[kind]
            response = event.get("response")
            if not isinstance(response, dict) or response.get("status") != expected_status:
                self._invalid("terminal_status_mismatch")
            else:
                self._response = deepcopy(response)
                if outcome == "succeeded" and (
                    response.get("error") is not None
                    or response.get("incomplete_details") is not None
                ):
                    self._invalid("completed_with_error_or_incomplete_details")
                else:
                    self._status, self._reason = outcome, expected_status
        # Metadata, per-item done events and future event types never imply success.
        return self.snapshot()

    def finish(self, transport_error: str | None = None) -> dict[str, Any]:
        if not self._closed:
            if self._status == "running":
                self._status = "incomplete"
                self._reason = (
                    "transport_interrupted:" + transport_error
                    if transport_error else "missing_terminal_event"
                )
            # A valid terminal response remains authoritative if transport closes
            # afterward. An error before a terminal can never become successful.
            self._closed = True
        return self.snapshot()


def judge_stream(events: Iterable[Any]) -> dict[str, Any]:
    judge = StreamJudge()
    try:
        for event in events:
            judge.feed(event)
    except OSError as exc:
        return judge.finish(transport_error=type(exc).__name__)
    return judge.finish()


def _row_outcome(row: dict[str, Any]) -> tuple[str, str]:
    error = row.get("error")
    response = row.get("response")
    if error is not None:
        if response is not None:
            return "protocol_error", "both_error_and_response"
        if not isinstance(error, dict) or not isinstance(error.get("code"), str):
            return "protocol_error", "malformed_error"
        code = error["code"]
        if code in {"expired", "cancelled", "canceled"}:
            return ("cancelled" if code == "canceled" else code), code
        return "failed", code
    if not isinstance(response, dict):
        return "protocol_error", "missing_response_or_error"
    code = response.get("status_code")
    if type(code) is not int or not 100 <= code <= 599:
        return "protocol_error", "invalid_http_status"
    if not 200 <= code < 300:
        return "failed", f"http_{code}"
    body = response.get("body")
    if not isinstance(body, dict):
        return "protocol_error", "malformed_body"
    status = body.get("status")
    if not isinstance(status, str):
        return "protocol_error", "unknown_or_missing_response_status"
    if status == "completed":
        if body.get("error") is not None or body.get("incomplete_details") is not None:
            return "protocol_error", "completed_with_error_or_incomplete_details"
        return "succeeded", "completed"
    if status in {"failed", "incomplete", "cancelled", "expired"}:
        return status, status
    if status in {"queued", "in_progress"}:
        return "incomplete", "response_not_completed"
    return "protocol_error", "unknown_or_missing_response_status"


def reconcile_batch(requested: Iterable[str], returned: Iterable[Any]) -> dict[str, Any]:
    """Join by custom_id and account for every request, without silently dropping rows.

    Missing means absent from this result collection, not proven service failure.
    Duplicate IDs are ambiguous, even when their records happen to be identical.
    """
    ids = list(requested)
    if any(not isinstance(key, str) or not key for key in ids):
        raise ValueError("requested custom_id values must be nonempty strings")
    if len(set(ids)) != len(ids):
        raise ValueError("requested custom_id values must be unique")
    expected = set(ids)
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    issues: list[dict[str, Any]] = []
    for index, row in enumerate(returned):
        if not isinstance(row, dict) or not isinstance(row.get("custom_id"), str) or not row["custom_id"]:
            issues.append({"type": "malformed_result", "index": index, "record": deepcopy(row)})
        elif row["custom_id"] not in expected:
            issues.append({"type": "unexpected_custom_id", "index": index, "record": deepcopy(row)})
        else:
            by_id[row["custom_id"]].append(deepcopy(row))
    items = []
    for key in ids:
        records = by_id[key]
        if not records:
            status, reason = "missing", "no_result_for_requested_id"
        elif len(records) > 1:
            status, reason = "protocol_error", "duplicate_custom_id"
        else:
            status, reason = _row_outcome(records[0])
        items.append({
            "custom_id": key, "status": status, "success": status == "succeeded",
            "reason": reason, "records": records,
        })
    counts = dict(Counter(item["status"] for item in items))
    reconciled = not issues and all(len(by_id[key]) == 1 for key in ids)
    return {
        "items": items,
        "counts": counts,
        "issues": issues,
        "fully_reconciled": reconciled,
        "success": reconciled and all(item["success"] for item in items),
    }


def run_fixture(path: Path) -> dict[str, Any]:
    fixture = json.loads(path.read_text(encoding="utf-8"))["fixture"]
    return {
        "evidence": "local_fixed_fixture_only",
        "stream": judge_stream(fixture["stream"]),
        "batch": reconcile_batch(fixture["batch_requested"], fixture["batch_returned"]),
    }


if __name__ == "__main__":
    print(json.dumps(run_fixture(Path(__file__).with_name("task.json")), ensure_ascii=False, indent=2))

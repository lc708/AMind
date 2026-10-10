"""Local fixed-fixture regression and contract tests; no SDK or network."""

import copy
import itertools
import json
import subprocess
import sys
import unittest
from pathlib import Path

from response_contract import ContractError, evaluate_fixture, match_batch, terminal_stream


ROOT = Path(__file__).resolve().parent


def completed(text="final"):
    return {"status": "completed", "id": "resp_fixed", "model": "fixture-only",
            "output": [{"type": "message", "phase": "final_answer", "content": [
                {"type": "output_text", "text": text}]}],
            "usage": {"input_tokens": 8, "output_tokens": 2}}


def row(key, body=None, code=200):
    return {"custom_id": key, "response": {"status_code": code,
            "body": completed() if body is None else body}, "error": None}


class StreamContracts(unittest.TestCase):
    def test_text_then_eof_is_disconnected(self):
        events = [{"type": "response.created"},
                  {"type": "response.output_text.delta", "delta": "Done"}]
        result = terminal_stream(events)
        self.assertEqual(result["status"], "disconnected")
        self.assertFalse(result["transport_success"])
        self.assertEqual(result["display_deltas"], "Done")
        self.assertIsNone(result["text"])
        self.assertIsNone(result["usage"])

    def test_empty_stream_is_disconnected(self):
        self.assertEqual(terminal_stream([])["status"], "disconnected")

    def test_completed_uses_final_response_not_provisional_deltas(self):
        body = completed("authoritative final")
        events = [{"type": "response.output_text.delta", "delta": "draft"},
                  {"type": "response.completed", "response": body}]
        original = copy.deepcopy(events)
        result = terminal_stream(events)
        self.assertTrue(result["transport_success"])
        self.assertEqual(result["text"], "authoritative final")
        self.assertEqual(result["display_deltas"], "draft")
        self.assertEqual(result["usage"], body["usage"])
        self.assertEqual(events, original)
        result["raw_response"]["output"][0]["phase"] = "changed"
        result["raw_events"][0]["delta"] = "changed"
        self.assertEqual(events, original)

    def test_completion_without_deltas_can_succeed(self):
        self.assertTrue(terminal_stream([
            {"type": "response.completed", "response": completed("")}]
        )["transport_success"])

    def test_failed_and_incomplete_preserve_partial_usage_and_reason(self):
        for status in ("failed", "incomplete"):
            with self.subTest(status=status):
                body = completed("partial")
                body.update(status=status, incomplete_details={"reason": "max_output_tokens"},
                            error={"code": "fixed_failure"})
                result = terminal_stream([{"type": "response." + status, "response": body}])
                self.assertFalse(result["transport_success"])
                self.assertEqual(result["status"], status)
                self.assertEqual(result["raw_response"], body)

    def test_error_after_delta_is_failure(self):
        error = {"type": "error", "code": "timeout", "message": "fixed fixture"}
        result = terminal_stream([
            {"type": "response.output_text.delta", "delta": "partial"}, error])
        self.assertEqual(result["status"], "stream_error")
        self.assertFalse(result["transport_success"])
        self.assertEqual(result["error"], error)

    def test_terminal_event_status_mismatch_rejected(self):
        with self.assertRaisesRegex(ContractError, "mismatch"):
            terminal_stream([{"type": "response.completed", "response": {"status": "failed"}}])

    def test_missing_terminal_body_rejected(self):
        with self.assertRaises(ContractError):
            terminal_stream([{"type": "response.completed"}])

    def test_events_after_terminal_or_error_rejected(self):
        for first in ({"type": "response.completed", "response": completed()},
                      {"type": "error", "code": "fixed"}):
            with self.subTest(first=first), self.assertRaisesRegex(ContractError, "after terminal"):
                terminal_stream([first, {"type": "response.created"}])

    def test_malformed_events_rejected(self):
        for event in (None, [], {}, {"type": "response.output_text.delta", "delta": 42}):
            with self.subTest(event=event), self.assertRaises(ContractError):
                terminal_stream([event])

    def test_unknown_events_do_not_imply_success(self):
        event = {"type": "future.event", "extra": {"kept": True}}
        result = terminal_stream([event])
        self.assertFalse(result["transport_success"])
        self.assertEqual(result["raw_events"], [event])

    def test_refusal_tools_and_opaque_items_are_preserved(self):
        body = completed()
        body["output"] = [
            {"type": "reasoning", "opaque": "fixture-state"},
            {"type": "function_call", "call_id": "call_fixed", "name": "lookup", "arguments": "{}"},
            {"type": "message", "phase": "final_answer", "content": [
                {"type": "refusal", "refusal": "fixed refusal"}]}]
        result = terminal_stream([{"type": "response.completed", "response": body}])
        self.assertTrue(result["transport_success"])
        self.assertEqual(result["refusals"], ["fixed refusal"])
        self.assertEqual(result["function_calls"], [body["output"][1]])
        self.assertEqual(result["raw_response"], body)
        self.assertNotIn("application_success", result)


class BatchContracts(unittest.TestCase):
    def test_every_result_permutation_matches_ids(self):
        rows = [row("a"), {"custom_id": "b", "error": {"code": "expired"}}, row("c")]
        for permutation in itertools.permutations(rows):
            result = match_batch(["a", "b", "c", "d"], permutation)
            self.assertEqual([r["custom_id"] for r in result["ordered"]], ["a", "b", "c", "d"])
            self.assertEqual([r["status"] for r in result["ordered"]],
                             ["completed", "batch_error", "completed", "missing"])
            self.assertEqual(result["missing"], ["d"])
            self.assertEqual(result["errors"], ["b"])
            self.assertFalse(result["all_transport_success"])

    def test_all_completed_batch(self):
        result = match_batch(["a", "b"], [row("b"), row("a")])
        self.assertTrue(result["all_transport_success"])
        self.assertEqual(result["counts"], {"completed": 2})

    def test_no_returned_rows_are_all_missing(self):
        result = match_batch(["a", "b"], [])
        self.assertEqual(result["missing"], ["a", "b"])
        self.assertFalse(result["all_transport_success"])

    def test_duplicate_requested_id_rejected(self):
        with self.assertRaisesRegex(ContractError, "duplicate request"):
            match_batch(["a", "a"], [])

    def test_duplicate_returned_id_rejected(self):
        with self.assertRaisesRegex(ContractError, "duplicate batch"):
            match_batch(["a"], [row("a"), row("a")])

    def test_unknown_id_rejected(self):
        with self.assertRaisesRegex(ContractError, "unknown batch"):
            match_batch(["a"], [row("unexpected")])

    def test_http_error_is_not_success(self):
        result = match_batch(["a"], [row("a", {"error": {"code": "rate_limit"}}, 429)])
        self.assertEqual(result["errors"], ["a"])
        self.assertEqual(result["ordered"][0]["status"], "http_error")

    def test_http_200_requires_completed_body(self):
        for status in ("failed", "incomplete", "in_progress", "unknown"):
            with self.subTest(status=status):
                body = {"status": status, "incomplete_details": {"reason": "fixture"}}
                result = match_batch(["a"], [row("a", body)])
                self.assertFalse(result["all_transport_success"])
                self.assertEqual(result["errors"], ["a"])
                self.assertEqual(result["ordered"][0]["response"]["raw_response"], body)

    def test_missing_body_status_cannot_succeed(self):
        result = match_batch(["a"], [row("a", {})])
        self.assertEqual(result["ordered"][0]["status"], "unknown")
        self.assertFalse(result["all_transport_success"])

    def test_raw_rows_preserved_without_mutating_input(self):
        rows = [row("a")]
        rows[0]["request_id"] = "request_fixed"
        original = copy.deepcopy(rows)
        result = match_batch(["a"], rows)
        self.assertEqual(result["ordered"][0]["raw"], original[0])
        result["ordered"][0]["raw"]["response"]["body"]["status"] = "modified"
        self.assertEqual(rows, original)

    def test_malformed_records_fail_closed(self):
        for bad in (None, {}, {"custom_id": "a"}, row("a", code=True),
                    row("a", code="200"), row("a", body=[]),
                    row("a", body={"status": "completed", "error": {"code": "contradiction"}})):
            with self.subTest(row=bad), self.assertRaises(ContractError):
                match_batch(["a"], [bad])


class OriginalFixtureAndCLI(unittest.TestCase):
    def test_original_fixture_and_legacy_regression(self):
        task = json.loads((ROOT / "task.json").read_text(encoding="utf-8"))
        original = copy.deepcopy(task)
        fixture = task["fixture"]
        # Reproduce exactly the two stated legacy rules, only as regression evidence.
        self.assertTrue(any(event.get("delta") for event in fixture["stream"]))
        legacy_pairs = list(zip(fixture["batch_requested"], fixture["batch_returned"]))
        self.assertNotEqual(legacy_pairs[0][0], legacy_pairs[0][1]["custom_id"])
        self.assertEqual(len(legacy_pairs), 2)  # Third request silently vanished.
        report = evaluate_fixture(task)
        self.assertEqual(report["stream"]["status"], "disconnected")
        self.assertFalse(report["stream"]["transport_success"])
        self.assertEqual([r["status"] for r in report["batch"]["ordered"]],
                         ["completed", "batch_error", "missing"])
        self.assertEqual(report["batch"]["ordered"][1]["error"]["code"], "expired")
        self.assertEqual(report["batch"]["missing"], ["c"])
        self.assertEqual(task, original)

    def test_public_cli(self):
        process = subprocess.run([sys.executable, str(ROOT / "response_contract.py"),
                                  str(ROOT / "task.json")],
                                 capture_output=True, text=True, check=True)
        report = json.loads(process.stdout)
        self.assertEqual(report["evidence"], "offline_fixed_fixture")
        self.assertEqual(report["batch"]["requested_count"], 3)
        self.assertFalse(report["batch"]["all_transport_success"])

    def test_cli_cannot_overwrite_input(self):
        path = ROOT / "task.json"
        before = path.read_bytes()
        process = subprocess.run([sys.executable, str(ROOT / "response_contract.py"),
                                  str(path), "--output", str(path)],
                                 capture_output=True, text=True)
        self.assertEqual(process.returncode, 2)
        self.assertIn("must not overwrite", process.stderr)
        self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)

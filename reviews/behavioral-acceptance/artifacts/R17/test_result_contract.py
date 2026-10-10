import copy
import itertools
import json
from pathlib import Path
import unittest

from result_contract import StreamJudge, judge_stream, reconcile_batch


FIXTURE = json.loads(Path(__file__).with_name("task.json").read_text())["fixture"]


def terminal(status="completed"):
    return {"type": "response." + status, "response": {"status": status}}


def result(key="a", code=200, status="completed"):
    return {"custom_id": key, "response": {"status_code": code, "body": {"status": status}}}


class StreamContractTests(unittest.TestCase):
    def test_original_text_is_not_success(self):
        events = copy.deepcopy(FIXTURE["stream"])
        self.assertTrue(any(e.get("delta") for e in events))  # old false positive
        actual = judge_stream(events)
        self.assertEqual(actual["status"], "incomplete")
        self.assertFalse(actual["success"])
        self.assertEqual(actual["reason"], "missing_terminal_event")
        self.assertEqual(actual["partial_text"], "Done")
        self.assertEqual(events, FIXTURE["stream"])

    def test_progress_is_provisional_until_terminal(self):
        judge = StreamJudge()
        self.assertFalse(judge.feed(FIXTURE["stream"][0])["success"])
        progress = judge.feed(FIXTURE["stream"][1])
        self.assertEqual(progress["status"], "running")
        self.assertFalse(progress["success"])
        self.assertTrue(judge.feed(terminal())["success"])
        self.assertTrue(judge.finish()["success"])

    def test_empty_stream_incomplete_and_empty_completed_response_success(self):
        self.assertEqual(judge_stream([])["status"], "incomplete")
        self.assertTrue(judge_stream([terminal()])["success"])

    def test_item_done_or_unknown_event_is_not_completion(self):
        for kind in ["response.output_text.done", "response.output_item.done", "future.event"]:
            with self.subTest(kind=kind):
                self.assertFalse(judge_stream([{"type": kind, "text": "Done"}])["success"])

    def test_non_success_terminal_after_text(self):
        for status in ["failed", "incomplete", "cancelled"]:
            with self.subTest(status=status):
                actual = judge_stream(FIXTURE["stream"] + [terminal(status)])
                self.assertEqual(actual["status"], status)
                self.assertFalse(actual["success"])
                self.assertEqual(actual["partial_text"], "Done")

    def test_error_after_partial_text(self):
        actual = judge_stream(FIXTURE["stream"] + [{"type": "error", "code": "overloaded"}])
        self.assertEqual(actual["status"], "failed")
        self.assertEqual(actual["partial_text"], "Done")

    def test_transport_failure_preserves_partial_text(self):
        def broken():
            yield from FIXTURE["stream"]
            raise ConnectionResetError("fixed mock disconnect")
        actual = judge_stream(broken())
        self.assertFalse(actual["success"])
        self.assertEqual(actual["reason"], "transport_interrupted:ConnectionResetError")
        self.assertEqual(actual["partial_text"], "Done")

    def test_completed_event_requires_consistent_response(self):
        cases = [
            {"type": "response.completed"},
            {"type": "response.completed", "response": {"status": "incomplete"}},
            {"type": "response.completed", "response": {"status": "completed", "error": {}}},
            {"type": "response.completed", "response": {"status": "completed", "incomplete_details": {}}},
        ]
        for event in cases:
            with self.subTest(event=event):
                self.assertEqual(judge_stream([event])["status"], "protocol_error")

    def test_malformed_event_cannot_be_repaired_by_later_success(self):
        for event in [None, {}, {"type": []}, {"type": "response.output_text.delta", "delta": 42}]:
            with self.subTest(event=event):
                self.assertEqual(judge_stream([event, terminal()])["status"], "protocol_error")

    def test_duplicate_or_trailing_terminal_rejected(self):
        for trailing in [terminal(), terminal("failed"), {"type": "response.output_text.delta", "delta": "late"}]:
            self.assertEqual(judge_stream([terminal(), trailing])["status"], "protocol_error")

    def test_finish_idempotent_and_feed_after_finish_rejected(self):
        judge = StreamJudge()
        first = judge.finish()
        self.assertEqual(judge.finish(), first)
        with self.assertRaises(RuntimeError):
            judge.feed(terminal())


class BatchContractTests(unittest.TestCase):
    def test_original_reordered_error_and_missing_results(self):
        rows = copy.deepcopy(FIXTURE["batch_returned"])
        actual = reconcile_batch(FIXTURE["batch_requested"], rows)
        self.assertEqual([(i["custom_id"], i["status"]) for i in actual["items"]],
                         [("a", "succeeded"), ("b", "expired"), ("c", "missing")])
        self.assertEqual(actual["counts"], {"succeeded": 1, "expired": 1, "missing": 1})
        self.assertFalse(actual["fully_reconciled"])
        self.assertFalse(actual["success"])
        self.assertEqual(rows, FIXTURE["batch_returned"])
        self.assertEqual(actual["items"][1]["records"][0]["error"]["code"], "expired")

    def test_every_result_permutation_has_same_join(self):
        rows = [result("a"), {"custom_id": "b", "error": {"code": "expired"}}, result("c")]
        expected = reconcile_batch(["a", "b", "c"], rows)
        for permutation in itertools.permutations(rows):
            self.assertEqual(reconcile_batch(["a", "b", "c"], permutation), expected)

    def test_all_success_and_null_error(self):
        row = result()
        row["error"] = None
        self.assertTrue(reconcile_batch(["a"], [row])["success"])

    def test_http_and_body_status_are_both_required(self):
        for code, status, expected in [
            (500, "completed", "failed"), (429, "completed", "failed"),
            (200, "incomplete", "incomplete"), (200, "failed", "failed"),
            (200, "in_progress", "incomplete"), (200, "new_status", "protocol_error"),
            (True, "completed", "protocol_error"), ("200", "completed", "protocol_error"),
            (200, [], "protocol_error"), (200, None, "protocol_error"),
        ]:
            with self.subTest(code=code, status=status):
                actual = reconcile_batch(["a"], [result(code=code, status=status)])
                self.assertEqual(actual["items"][0]["status"], expected)
                self.assertFalse(actual["success"])

    def test_duplicate_results_never_overwrite(self):
        for second in [result(), result(code=500)]:
            actual = reconcile_batch(["a"], [result(), second])
            self.assertEqual(actual["items"][0]["reason"], "duplicate_custom_id")
            self.assertEqual(len(actual["items"][0]["records"]), 2)
            self.assertFalse(actual["success"])
            self.assertFalse(actual["fully_reconciled"])

    def test_unknown_and_malformed_results_are_visible(self):
        for bad in [None, {}, {"custom_id": []}, result("unexpected")]:
            actual = reconcile_batch(["a"], [result(), bad])
            self.assertTrue(actual["items"][0]["success"])
            self.assertEqual(len(actual["issues"]), 1)
            self.assertFalse(actual["success"])

    def test_malformed_payload_and_conflicting_success_fail_closed(self):
        cases = [
            {"custom_id": "a"}, {"custom_id": "a", "error": {}},
            {**result(), "error": {"code": "expired"}},
            {"custom_id": "a", "response": {"status_code": 200, "body": None}},
            {"custom_id": "a", "response": {"status_code": 200, "body": {"status": "completed", "error": {}}}},
        ]
        for row in cases:
            self.assertEqual(reconcile_batch(["a"], [row])["items"][0]["status"], "protocol_error")

    def test_invalid_request_ids_rejected(self):
        for ids in [["a", "a"], [""], [None], [[]]]:
            with self.assertRaises(ValueError):
                reconcile_batch(ids, [])

    def test_empty_and_entirely_missing_batches(self):
        self.assertTrue(reconcile_batch([], [])["success"])
        self.assertEqual(reconcile_batch(["a", "b"], [])["counts"], {"missing": 2})


if __name__ == "__main__":
    unittest.main(verbosity=2)

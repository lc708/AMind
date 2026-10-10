from copy import deepcopy
import json
from pathlib import Path
import unittest

from demo import message, run_demo
from integration import Session, ProtocolError, ContinuationBlocked, parse_response
import legacy


FIXTURE = json.loads((Path(__file__).parent / "task.json").read_text())["fixture"]


def response(*items, status="completed", **kwargs):
    return {"status": status, "output": list(items), **kwargs}


def call(call_id="c1", arguments="{}"):
    return {"type": "function_call", "call_id": call_id,
            "name": "lookup", "arguments": arguments}


def session():
    return Session(scope="tenant-a:resource-1", config={"model": "configured-fixture-model",
                   "instructions": "Keep instructions", "max_output_tokens": 100,
                   "custom_setting": {"opaque": True}},
                   history=[{"role": "user", "content": "lookup"}])


class ParserTests(unittest.TestCase):
    def test_given_response_reproduces_old_failure_and_preserves_all_items(self):
        raw = deepcopy(FIXTURE["response_fixture"])
        with self.assertRaises(KeyError):
            legacy.parse(raw)
        parsed = parse_response(raw)
        self.assertEqual(parsed["display_text"], "Working")
        self.assertEqual(parsed["commentary_text"], "Working")
        self.assertEqual(parsed["outcome"], "tool_required")
        self.assertFalse(parsed["task_complete"])
        self.assertIsNone(parsed["final_text"])
        self.assertEqual(parsed["output_items"], raw["output"])
        self.assertEqual(json.loads(json.dumps(parsed["raw_response"])), raw)

    def test_legacy_plain_text_contract_is_unchanged(self):
        raw = response(message("Hello"))
        del raw["output"][0]["phase"]
        self.assertEqual(parse_response(raw)["final_text"], legacy.parse(raw))

    def test_legacy_history_loses_state_while_new_history_keeps_it(self):
        old_history = []
        legacy.append_rendered_text(old_history, "Working")
        current = session()
        current.accept(FIXTURE["response_fixture"], delivery_id="r1")
        self.assertNotEqual(old_history, FIXTURE["response_fixture"]["output"])
        self.assertEqual(current.history[1:], FIXTURE["response_fixture"]["output"])

    def test_final_text_with_tool_call_still_requires_continuation(self):
        parsed = parse_response(response(message("Done?"), call()))
        self.assertEqual(parsed["outcome"], "tool_required")
        self.assertIsNone(parsed["final_text"])
        self.assertFalse(parsed["task_complete"])

    def test_multiple_messages_and_content_are_extracted_in_order(self):
        a = message("A")
        a["content"].append({"type": "output_text", "text": "B"})
        self.assertEqual(parse_response(response(a, message("C")))["final_text"], "ABC")

    def test_commentary_then_final_is_not_flattened_for_completion(self):
        parsed = parse_response(response(message("Working", "commentary"), message("Done")))
        self.assertEqual(parsed["display_text"], "WorkingDone")
        self.assertEqual(parsed["final_text"], "Done")
        self.assertFalse(parse_response(response(message("Working", "commentary")))["task_complete"])

    def test_unknown_phase_is_preserved_but_not_final(self):
        raw = response(message("Maybe", "future_phase"))
        parsed = parse_response(raw)
        self.assertFalse(parsed["task_complete"])
        self.assertEqual(parsed["raw_response"], raw)

    def test_failure_fixture_preserves_reason_usage_and_blocks_success(self):
        parsed = parse_response(FIXTURE["failure_fixture"])
        self.assertEqual(parsed["outcome"], "incomplete")
        self.assertEqual(parsed["usage"], {"output_tokens": 100})
        self.assertEqual(parsed["incomplete_details"], {"reason": "max_output_tokens"})
        self.assertIsNone(parsed["final_text"])

    def test_noncompleted_text_never_claims_success(self):
        for status in ("incomplete", "failed", "cancelled", "queued", "in_progress", "future_status", "final"):
            with self.subTest(status=status):
                parsed = parse_response(response(message("Partial"), status=status,
                                                error={"code": "fixture"}, usage={"output_tokens": 4}))
                self.assertFalse(parsed["task_complete"])
                self.assertIsNone(parsed["final_text"])
                self.assertEqual(parsed["display_text"], "Partial")
                self.assertEqual(parsed["error"], {"code": "fixture"})
                self.assertEqual(parsed["usage"]["output_tokens"], 4)
                if status == "final":
                    self.assertEqual(parsed["outcome"], "unknown_status")

    def test_refusal_is_separate_observable_outcome(self):
        raw = response({"type": "message", "role": "assistant", "content":
                        [{"type": "refusal", "refusal": "Cannot fulfill"}]})
        parsed = parse_response(raw)
        self.assertEqual(parsed["outcome"], "refused")
        self.assertEqual(parsed["refusals"], ["Cannot fulfill"])
        self.assertFalse(parsed["task_complete"])

    def test_opaque_unknown_fields_round_trip_and_no_aliasing(self):
        raw = response({"type": "compaction", "encrypted_content": "opaque-fixed"},
                       {"type": "future_item", "unknown": {"nested": [1, 2]}})
        parsed = parse_response(raw)
        self.assertEqual(parsed["raw_response"], raw)
        parsed["output_items"][1]["unknown"]["nested"].append(3)
        self.assertEqual(raw["output"][1]["unknown"]["nested"], [1, 2])

    def test_malformed_response_is_not_hidden_as_empty_success(self):
        for raw in (None, {}, {"status": "completed", "output": {}},
                    response(1), response({"type": "message", "content": "bad"}),
                    response({"type": "message", "content": [{"type": "output_text", "text": 3}]})):
            with self.subTest(raw=raw), self.assertRaises(ProtocolError):
                parse_response(raw)


class ContinuationTests(unittest.TestCase):
    def test_exact_given_output_precedes_corresponding_result(self):
        current = session()
        current.accept(FIXTURE["response_fixture"], delivery_id="r1")
        with self.assertRaises(ContinuationBlocked):
            current.request()
        current.record_tool_result("c1", '{"ok":true}')
        request = current.request()
        self.assertEqual(request["input"][1:4], FIXTURE["response_fixture"]["output"])
        self.assertEqual(request["input"][4], {"type": "function_call_output",
                                               "call_id": "c1", "output": '{"ok":true}'})
        self.assertEqual(request["model"], "configured-fixture-model")
        self.assertEqual(request["instructions"], "Keep instructions")
        self.assertEqual(request["max_output_tokens"], 100)
        self.assertNotIn("previous_response_id", request)
        self.assertNotIn("conversation", request)

    def test_multiple_tools_all_must_resolve(self):
        current = session()
        current.accept(response(call("c1"), call("c2")), delivery_id="r1")
        current.record_tool_result("c2", "second")
        with self.assertRaises(ContinuationBlocked):
            current.request()
        current.record_tool_result("c1", "first")
        self.assertEqual(current.pending_calls, [])
        self.assertEqual([x.get("call_id") for x in current.request()["input"][3:]], ["c2", "c1"])

    def test_bad_tool_arguments_leave_state_atomic(self):
        for arguments in ("bad json", "[]", "null", "", {"x": 1}):
            current = session()
            before = current.snapshot()
            with self.subTest(arguments=arguments), self.assertRaises(ProtocolError):
                current.accept(response(call(arguments=arguments)), delivery_id="r1")
            self.assertEqual(current.snapshot(), before)

    def test_orphan_and_conflicting_duplicate_result_rejected(self):
        current = session()
        with self.assertRaises(ProtocolError):
            current.record_tool_result("missing", "x")
        current.accept(response(call()), delivery_id="r1")
        self.assertTrue(current.record_tool_result("c1", "ok"))
        before = current.snapshot()
        self.assertFalse(current.record_tool_result("c1", "ok"))
        with self.assertRaises(ProtocolError):
            current.record_tool_result("c1", "different")
        self.assertEqual(current.snapshot(), before)

    def test_replayed_delivery_noops_and_conflict_rejected(self):
        current = session()
        raw = response(call())
        current.accept(raw, delivery_id="r1")
        before = current.snapshot()
        current.accept(raw, delivery_id="r1")
        self.assertEqual(current.snapshot(), before)
        with self.assertRaises(ProtocolError):
            current.accept(response(message("Different")), delivery_id="r1")

    def test_reused_call_id_rejected_even_after_result(self):
        current = session()
        current.accept(response(call()), delivery_id="r1")
        current.record_tool_result("c1", "ok")
        with self.assertRaises(ProtocolError):
            current.accept(response(call()), delivery_id="r2")

    def test_failed_tool_result_is_preserved_without_success_invention(self):
        current = session()
        current.accept(response(call()), delivery_id="r1")
        failure = json.dumps({"ok": False, "error": "mock timeout"})
        current.record_tool_result("c1", failure)
        self.assertEqual(current.request()["input"][-1]["output"], failure)

    def test_failure_is_journaled_and_cannot_continue_or_dispatch(self):
        current = session()
        history = current.history
        current.accept(FIXTURE["failure_fixture"], delivery_id="r1")
        self.assertEqual(current.history, history)
        self.assertEqual(current.snapshot()["responses"]["r1"], FIXTURE["failure_fixture"])
        with self.assertRaises(ContinuationBlocked):
            current.request()
        with self.assertRaises(ContinuationBlocked):
            current.record_tool_result("c1", "result")

    def test_reconnect_before_and_after_tool_output_round_trips(self):
        current = session()
        current.accept(FIXTURE["response_fixture"], delivery_id="r1")
        for resolved in (False, True):
            if resolved:
                current.record_tool_result("c1", "ok")
            restored = Session.restore(json.loads(json.dumps(current.snapshot())),
                                       expected_scope=current.scope)
            self.assertEqual(restored.snapshot(), current.snapshot())
            self.assertEqual(restored.pending_calls, current.pending_calls)
            if resolved:
                self.assertEqual(restored.request(), current.request())

    def test_scope_and_state_owner_mismatch_rejected(self):
        current = session()
        for expected in ("tenant-b:resource-1", "tenant-a:resource-2"):
            with self.assertRaises(ProtocolError):
                Session.restore(current.snapshot(), expected_scope=expected)
        for key in ("previous_response_id", "conversation", "input"):
            with self.assertRaises(ProtocolError):
                Session(scope="x", config={key: "value"}, history=[])

    def test_cancellation_survives_snapshot_and_prevents_continuation(self):
        current = session()
        current.accept(response(call()), delivery_id="r1")
        current.cancel()
        restored = Session.restore(current.snapshot(), expected_scope=current.scope)
        with self.assertRaises(ContinuationBlocked):
            restored.request()
        with self.assertRaises(ContinuationBlocked):
            restored.record_tool_result("c1", "ok")

    def test_plain_continuation_and_opaque_compacted_input(self):
        compacted = {"type": "compaction", "encrypted_content": "fixed-opaque-never-decode"}
        current = Session(scope="x", config={}, history=[compacted])
        current.append_input([{"role": "user", "content": "continue"}])
        current.accept(response(message("Done")), delivery_id="r1")
        current.append_input([{"role": "user", "content": "next"}])
        self.assertEqual(current.request()["input"][0], compacted)
        self.assertEqual(len(current.request()["input"]), 4)

    def test_mutating_requests_and_snapshots_cannot_corrupt_session(self):
        current = session()
        request = current.request()
        request["custom_setting"]["opaque"] = False
        request["input"].clear()
        snapshot = current.snapshot()
        snapshot["history"].clear()
        self.assertEqual(len(current.history), 1)
        self.assertTrue(current.request()["custom_setting"]["opaque"])

    def test_user_input_cannot_inject_protocol_call_items(self):
        current = session()
        with self.assertRaises(ProtocolError):
            current.append_input([{**call(), "role": "user"}])
        self.assertEqual(len(current.history), 1)

    def test_public_demo_uses_supplied_fixtures_and_finishes_with_mock(self):
        result, trace = run_demo()
        self.assertEqual(result["first"]["raw_response"], FIXTURE["response_fixture"])
        self.assertEqual(result["failure"]["raw_response"], FIXTURE["failure_fixture"])
        self.assertEqual(result["final"]["outcome"], "final")
        self.assertEqual(result["baseline"]["exception"], "KeyError")
        self.assertEqual(len(trace), 2)


if __name__ == "__main__":
    unittest.main()

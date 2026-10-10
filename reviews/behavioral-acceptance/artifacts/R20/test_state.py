"""Regression suite using fixed local data only; no SDK, provider, or I/O tools."""
import copy
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from state import (ResponseChain, StateError, client_compaction_request, diagnose,
                   final_messages, fingerprint, result_from_call)


FIXTURE = json.loads(Path(__file__).with_name("task.json").read_text())["fixture"]
SCOPE = "fixture:tenant-a:resource-a"


class StateTests(unittest.TestCase):
    def setUp(self):
        self.no_network = patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden"))
        self.no_network.start()
        self.addCleanup(self.no_network.stop)
        self.previous = copy.deepcopy(FIXTURE["previous_response"])
        self.call = self.previous["output"][1]
        self.result = result_from_call(self.call, "invoice")
        self.user = copy.deepcopy(FIXTURE["next_request"]["input"][0])
        self.state = ResponseChain(self.previous, SCOPE)

    def error(self, code, fn):
        with self.assertRaises(StateError) as caught:
            fn()
        self.assertEqual(caught.exception.code, code)

    def prepare(self, results=None, users=None):
        return self.state.prepare([self.user] if users is None else users,
                                  [self.result] if results is None else results, scope=SCOPE)

    def test_original_failure_is_reproduced(self):
        findings = diagnose(self.previous, FIXTURE["next_request"])
        self.assertEqual({x["code"] for x in findings}, {
            "assistant_in_chain_input", "phase_drift", "orphan_tool_result", "unresolved_tool_calls"})
        wrong = FIXTURE["next_request"]["input"][2]
        self.error("orphan_tool_result", lambda: self.prepare([wrong]))

    def test_corrected_exact_envelope_and_original_preserved(self):
        before = copy.deepcopy(FIXTURE)
        request = self.prepare()
        self.assertEqual(request, {"previous_response_id": "r1", "input": [self.user, self.result]})
        self.assertEqual(diagnose(self.previous, request), [])
        self.assertEqual(FIXTURE, before)
        self.assertEqual(self.state.response, self.previous)

    def test_phase_retained_after_json_storage_and_not_a_final_answer(self):
        response = self.state.response
        self.assertEqual(response["output"][0]["phase"], "commentary")
        restored = ResponseChain.restore(json.loads(json.dumps(self.state.snapshot())), scope=SCOPE)
        self.assertEqual(restored.response, response)
        self.assertEqual(final_messages(response), [])

    def test_replayed_assistant_cannot_enter_fresh_input(self):
        self.error("fresh_input_must_be_user_message", lambda: self.prepare(users=[self.previous["output"][0]]))

    def test_multiple_calls_match_ids_not_array_positions(self):
        second = dict(self.call, call_id="c2", name="other_read")
        self.previous["output"].append(second)
        self.state = ResponseChain(self.previous, SCOPE)
        results = [result_from_call(second, "second"), self.result]
        request = self.prepare(results)
        self.assertEqual([x["call_id"] for x in request["input"][1:]], ["c2", "c1"])
        self.assertEqual(diagnose(self.previous, request), [])

    def test_missing_and_duplicate_results_rejected(self):
        self.error("unresolved_tool_calls", lambda: self.prepare([]))
        self.error("duplicate_tool_result", lambda: self.prepare([self.result, self.result]))

    def test_malformed_result_rejected(self):
        for malformed, code in (({"type": "message"}, "malformed_tool_result"),
                                (dict(self.result, output=42), "tool_output_must_be_string"),
                                (dict(self.result, call_id=None), "orphan_tool_result")):
            with self.subTest(code=code):
                self.error(code, lambda: self.prepare([malformed]))

    def test_malformed_arguments_rejected(self):
        for args in ("{bad", "[]", "null", {}, "42"):
            with self.subTest(args=args):
                response = copy.deepcopy(self.previous)
                response["output"][1]["arguments"] = args
                self.error("malformed_arguments", lambda: ResponseChain(response, SCOPE))

    def test_failed_and_timed_out_tools_preserve_failure_evidence(self):
        for code in ("read_failed", "timeout"):
            with self.subTest(code=code):
                state = ResponseChain(self.previous, SCOPE)
                output = json.dumps({"ok": False, "error": code})
                result = result_from_call(self.call, output)
                request = state.prepare([], [result], scope=SCOPE)
                self.assertEqual(json.loads(request["input"][0]["output"]), {"ok": False, "error": code})
                self.assertEqual(final_messages(state.response), [])

    def test_commentary_then_final_with_two_tool_rounds(self):
        request = self.prepare()
        second = {"id": "r2", "status": "completed", "output": [
            dict(self.previous["output"][0], content="Checking"), dict(self.call, call_id="c2")]}
        self.state.accept(request, second, scope=SCOPE)
        self.assertEqual(final_messages(self.state.response), [])
        request2 = self.state.prepare([], [result_from_call(second["output"][1], "invoice")], scope=SCOPE)
        final = {"id": "r3", "status": "completed", "output": [
            {"type": "message", "role": "assistant", "phase": "final_answer", "content": "invoice"}]}
        self.state.accept(request2, final, scope=SCOPE)
        self.assertEqual(final_messages(self.state.response), final["output"])
        self.assertEqual(request2["previous_response_id"], "r2")
        self.assertNotIn("Working", json.dumps(request2))

    def test_plain_continuations_do_not_accumulate_history(self):
        state = ResponseChain({"id": "plain0", "status": "completed", "output": []}, SCOPE)
        for n in range(1, 6):
            request = state.prepare([dict(self.user, content=str(n))], [], scope=SCOPE)
            self.assertEqual(len(request["input"]), 1)
            self.assertEqual(request["previous_response_id"], "plain" + str(n - 1))
            response = {"id": "plain" + str(n), "status": "completed", "output": [
                {"type": "message", "role": "assistant", "phase": "final_answer", "content": str(n)}]}
            state.accept(request, response, scope=SCOPE)

    def test_settings_are_explicit_each_turn_and_preserved(self):
        settings = {"instructions": "Keep supplied instructions", "model": "configured-fixture-model"}
        request = self.state.prepare([], [self.result], scope=SCOPE, settings=settings)
        self.assertEqual(request["model"], settings["model"])
        self.assertEqual(request["instructions"], settings["instructions"])
        self.state.accept(request, {"id": "r2", "status": "completed", "output": []}, scope=SCOPE)
        next_request = self.state.prepare([self.user], [], scope=SCOPE,
                                          settings={"instructions": "Explicit update", "model": settings["model"]})
        self.assertEqual(next_request["instructions"], "Explicit update")

    def test_mixed_owners_and_wrong_parent_cannot_override_envelope(self):
        for key, value in (("conversation", "conv"), ("previous_response_id", "wrong"), ("input", [])):
            self.error("mixed_state_owners", lambda: self.state.prepare(
                [], [self.result], scope=SCOPE, settings={key: value}))

    def test_returned_snapshots_and_requests_cannot_mutate_storage(self):
        request = self.prepare()
        request["input"][0]["content"] = "mutation"
        snapshot = self.state.snapshot()
        snapshot["response"]["output"][0]["phase"] = "final_answer"
        self.assertEqual(self.state.response, self.previous)
        self.assertEqual(self.prepare()["input"][0], self.user)

    def test_reconnect_retains_exact_prepared_request(self):
        request = self.prepare()
        restored = ResponseChain.restore(json.loads(json.dumps(self.state.snapshot())), scope=SCOPE)
        self.assertEqual(restored.prepare([self.user], [self.result], scope=SCOPE), request)
        self.error("inflight_request_changed", lambda: restored.prepare([], [self.result], scope=SCOPE))

    def test_cancelled_session_rejects_send_and_advance_after_restore(self):
        request = self.prepare()
        self.state.cancel()
        restored = ResponseChain.restore(self.state.snapshot(), scope=SCOPE)
        self.error("cancelled", lambda: restored.prepare([], [self.result], scope=SCOPE))
        self.error("cancelled", lambda: restored.accept(request, {"id": "r2", "output": []}, scope=SCOPE))

    def test_non_success_response_blocks_continuation_and_final(self):
        for status in ("failed", "incomplete", "cancelled", "in_progress"):
            with self.subTest(status=status):
                state = ResponseChain(dict(self.previous, status=status), SCOPE)
                self.error("response_not_completed", lambda: state.prepare([], [self.result], scope=SCOPE))
                self.assertEqual(final_messages(state.response), [])

    def test_unknown_status_is_structural_only_not_success(self):
        self.assertNotIn("status", self.state.response)
        self.prepare()
        self.assertEqual(final_messages(self.state.response), [])

    def test_cross_tenant_and_resource_rejected(self):
        for other in ("fixture:tenant-b:resource-a", "fixture:tenant-a:resource-b"):
            with self.subTest(other=other):
                self.error("scope_mismatch", lambda: self.state.prepare([], [self.result], scope=other))
                self.error("scope_mismatch", lambda: ResponseChain.restore(self.state.snapshot(), scope=other))

    def test_duplicate_response_and_reused_call_rejected(self):
        request = self.prepare()
        self.error("duplicate_response_id", lambda: self.state.accept(request, self.previous, scope=SCOPE))
        self.error("reused_call_id", lambda: self.state.accept(request, dict(self.previous, id="r2"), scope=SCOPE))

    def test_advance_requires_exact_prepared_request(self):
        request = self.prepare()
        wrong = dict(request, previous_response_id="wrong")
        self.error("unrecognized_request", lambda: self.state.accept(wrong, {"id": "r2", "output": []}, scope=SCOPE))

    def test_server_compaction_output_stays_opaque_on_resume(self):
        request = self.prepare()
        response = {"id": "r2", "status": "completed", "output": [FIXTURE["later_compaction"]]}
        self.state.accept(request, response, scope=SCOPE)
        restored = ResponseChain.restore(json.loads(json.dumps(self.state.snapshot())), scope=SCOPE)
        self.assertEqual(restored.response["output"], response["output"])
        next_request = restored.prepare([self.user], [], scope=SCOPE)
        self.assertEqual(next_request, {"previous_response_id": "r2", "input": [self.user]})
        self.assertNotIn("opaque-2", json.dumps(next_request))

    def test_client_compaction_preserves_complete_fixed_output_and_order(self):
        # Synthetic complete output envelope around the supplied opaque item.
        # It tests serialization only, not the service's compact behavior.
        compact = [{"role": "user", "content": "retained " * 20000},
                   copy.deepcopy(FIXTURE["later_compaction"])]
        digest = fingerprint(compact)
        request = client_compaction_request(compact, [self.user], expected_hash=digest,
                                             source_scope=SCOPE, scope=SCOPE)
        self.assertEqual(request["input"][:-1], compact)
        self.assertEqual(request["input"][-1], self.user)
        self.assertEqual(fingerprint(request["input"][:-1]), digest)
        self.assertNotIn("previous_response_id", request)

    def test_mutated_or_missing_compaction_is_rejected(self):
        compact = [copy.deepcopy(FIXTURE["later_compaction"])]
        digest = fingerprint(compact)
        compact[0]["encrypted_content"] += "corrupted"
        self.error("changed_compaction", lambda: client_compaction_request(
            compact, [], expected_hash=digest, source_scope=SCOPE, scope=SCOPE))
        self.error("missing_compaction", lambda: client_compaction_request(
            [], [], expected_hash=fingerprint([]), source_scope=SCOPE, scope=SCOPE))

    def test_compaction_rejects_wrong_scope_and_mixed_owner(self):
        compact = [FIXTURE["later_compaction"]]
        self.error("scope_mismatch", lambda: client_compaction_request(
            compact, [], expected_hash=fingerprint(compact), source_scope=SCOPE, scope="other"))
        self.error("mixed_state_owners", lambda: client_compaction_request(
            compact, [], expected_hash=fingerprint(compact), source_scope=SCOPE, scope=SCOPE,
            settings={"previous_response_id": "r1"}))

    def test_one_change_ablation_does_not_hide_other_failures(self):
        original = FIXTURE["next_request"]
        phase_only = copy.deepcopy(original)
        phase_only["input"][1]["phase"] = "commentary"
        phase_codes = {x["code"] for x in diagnose(self.previous, phase_only)}
        self.assertNotIn("phase_drift", phase_codes)
        self.assertIn("orphan_tool_result", phase_codes)
        self.assertIn("assistant_in_chain_input", phase_codes)
        id_only = copy.deepcopy(original)
        id_only["input"][2] = self.result
        id_codes = {x["code"] for x in diagnose(self.previous, id_only)}
        self.assertEqual(id_codes, {"phase_drift", "assistant_in_chain_input"})
        owner_only = copy.deepcopy(original)
        owner_only["input"].pop(1)
        self.assertEqual({x["code"] for x in diagnose(self.previous, owner_only)},
                         {"orphan_tool_result", "unresolved_tool_calls"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

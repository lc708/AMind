from copy import deepcopy
import json
from pathlib import Path
import unittest

from integration import (ProtocolError, parse_response, replay_history,
                         prepare_continuation, parse_tool_arguments,
                         checkpoint, restore_checkpoint)

TASK = json.loads(Path(__file__).with_name("task.json").read_text())
GOOD = TASK["fixture"]["response_fixture"]
BAD = TASK["fixture"]["failure_fixture"]


def message(text, phase="final_answer"):
    result = {"type": "message", "role": "assistant",
              "content": [{"type": "output_text", "text": text}]}
    if phase is not None:
        result["phase"] = phase
    return result


def response(*items, status="completed"):
    return {"status": status, "output": list(items)}


def result(call_id="c1"):
    return {"type": "function_call_output", "call_id": call_id, "output": "fixed-result"}


class IntegrationTests(unittest.TestCase):
    def test_original_parser_fails_both_supplied_fixtures(self):
        with self.assertRaises(KeyError):
            GOOD["output"][0]["content"][0]["text"]
        with self.assertRaises(IndexError):
            BAD["output"][0]["content"][0]["text"]

    def test_supplied_mixed_fixture_is_progress_and_tool_not_final(self):
        parsed = parse_response(GOOD)
        self.assertEqual(parsed.state, "needs_tools")
        self.assertEqual(parsed.progress_text, "Working")
        self.assertIsNone(parsed.final_text)
        self.assertEqual([c["call_id"] for c in parsed.tool_calls], ["c1"])
        self.assertNotIn("opaque-1", parsed.progress_text)

    def test_supplied_incomplete_is_not_empty_success(self):
        parsed = parse_response(BAD)
        self.assertEqual(parsed.state, "incomplete")
        self.assertIsNone(parsed.final_text)
        self.assertEqual(parsed.usage, {"output_tokens": 100})
        self.assertIn("incomplete: max_output_tokens", parsed.diagnostics)
        self.assertEqual(parsed.raw, BAD)
        with self.assertRaises(ProtocolError):
            prepare_continuation([], BAD)

    def test_legacy_plain_response_unchanged(self):
        old = response(message("hello", phase=None))
        self.assertEqual(parse_response(old).final_text,
                         old["output"][0]["content"][0]["text"])

    def test_multiple_text_blocks_and_messages_in_order(self):
        first = message("A")
        first["content"].append({"type": "output_text", "text": "B"})
        parsed = parse_response(response({"type": "reasoning", "encrypted_content": "hidden"}, first, message("C")))
        self.assertEqual(parsed.final_text, "AB\nC")

    def test_commentary_without_tool_requires_continuation(self):
        parsed = parse_response(response(message("Working", "commentary")))
        self.assertEqual(parsed.state, "needs_continuation")
        self.assertIsNone(parsed.final_text)

    def test_empty_completed_is_not_final(self):
        self.assertEqual(parse_response(response()).state, "needs_continuation")
        self.assertEqual(parse_response(response(message(""))).state, "needs_continuation")

    def test_tool_call_prevents_premature_final(self):
        data = deepcopy(GOOD)
        data["output"].append(message("Candidate answer"))
        self.assertEqual(parse_response(data).state, "needs_tools")
        self.assertIsNone(parse_response(data).final_text)

    def test_full_replay_preserves_prefix_and_every_field(self):
        history = [{"role": "system", "content": TASK["constraints"]},
                   {"role": "user", "content": TASK["request"]}]
        data = deepcopy(GOOD)
        data["output"][0]["extra_metadata"] = {"nested": [1, 2]}
        before_history, before_data = deepcopy(history), deepcopy(data)
        next_input = prepare_continuation(history, data, [result()])
        self.assertEqual(next_input, history + data["output"] + [result()])
        self.assertEqual(next_input[3]["phase"], "commentary")
        next_input[2]["extra_metadata"]["nested"].append(3)
        self.assertEqual(history, before_history)
        self.assertEqual(data, before_data)

    def test_checkpoint_roundtrip_preserves_envelope_and_opaque_content(self):
        history = [{"role": "user", "content": "原始输入"}]
        restored = restore_checkpoint(checkpoint(history, GOOD, "turn-1"))
        self.assertEqual(restored["history_before_response"], history)
        self.assertEqual(restored["response"], GOOD)
        self.assertEqual(restored["response"]["output"][0]["encrypted_content"], "opaque-1")
        self.assertEqual(prepare_continuation(history, GOOD, [result()]),
                         prepare_continuation(restored["history_before_response"], restored["response"], [result()]))
        failure = restore_checkpoint(checkpoint(history, BAD, "turn-2"))
        self.assertEqual(failure["response"]["incomplete_details"], BAD["incomplete_details"])

    def test_checkpoint_rejects_bad_version_or_missing_identity(self):
        with self.assertRaises(ProtocolError):
            restore_checkpoint('{"version": 99}')
        with self.assertRaises(ProtocolError):
            checkpoint([], GOOD, "")

    def test_parallel_results_are_complete_and_ordered_by_calls(self):
        data = deepcopy(GOOD)
        data["output"].append({"type": "function_call", "call_id": "c2", "name": "lookup", "arguments": "{}"})
        built = prepare_continuation([], data, [result("c2"), result("c1")])
        self.assertEqual(built, data["output"] + [result("c1"), result("c2")])

    def test_missing_duplicate_and_unrelated_results_rejected(self):
        for supplied in ([], [result(), result()], [result("wrong")]):
            with self.subTest(supplied=supplied), self.assertRaises(ProtocolError):
                prepare_continuation([], GOOD, supplied)

    def test_duplicate_call_ids_rejected(self):
        data = deepcopy(GOOD)
        data["output"].append(deepcopy(data["output"][-1]))
        with self.assertRaises(ProtocolError):
            parse_response(data)

    def test_unknown_types_preserved_without_auto_execution(self):
        data = deepcopy(GOOD)
        data["output"].append({"type": "future_item", "opaque": {"a": [1, 2]}})
        self.assertEqual(parse_response(data).state, "unsupported")
        self.assertEqual(replay_history([], data), data["output"])
        with self.assertRaises(ProtocolError):
            prepare_continuation([], data, [result()])

    def test_unknown_phase_preserved_without_becoming_final(self):
        data = response(message("progress", "future_phase"))
        self.assertEqual(parse_response(data).state, "unsupported")
        self.assertEqual(replay_history([], data), data["output"])

    def test_incomplete_even_with_text_and_parseable_tool_never_continues(self):
        data = deepcopy(GOOD)
        data.update(status="incomplete", incomplete_details={"reason": "max_output_tokens"})
        data["output"].append(message("partial"))
        self.assertEqual(parse_response(data).state, "incomplete")
        self.assertIsNone(parse_response(data).final_text)
        with self.assertRaises(ProtocolError):
            prepare_continuation([], data, [result()])

    def test_refusal_with_tool_cannot_continue(self):
        data = deepcopy(GOOD)
        data["output"].append({"type": "message", "role": "assistant", "content": [{"type": "refusal", "refusal": "Declined"}]})
        self.assertEqual(parse_response(data).state, "refused")
        with self.assertRaises(ProtocolError):
            prepare_continuation([], data, [result()])

    def test_noncompleted_statuses_do_not_publish_answer(self):
        for status, expected in (("failed", "failed"), ("cancelled", "cancelled"),
                                 ("queued", "pending"), ("in_progress", "pending"),
                                 ("new-status", "unsupported")):
            with self.subTest(status=status):
                parsed = parse_response(response(message("not final"), status=status))
                self.assertEqual(parsed.state, expected)
                self.assertIsNone(parsed.final_text)

    def test_malformed_shapes_are_explicit_protocol_errors(self):
        for data in ({}, {"output": None}, response(None), response({"type": "message", "role": "assistant", "content": "bad"}), response(message(42))):
            with self.subTest(data=data), self.assertRaises(ProtocolError):
                parse_response(data)

    def test_strict_arguments_and_schema_validation(self):
        self.assertEqual(parse_tool_arguments(GOOD["output"][-1], lambda args: args == {}), {})
        for arguments in ('{"x":', '[]', '{"x":NaN}', '{"x":1,"x":2}', '{} garbage'):
            with self.subTest(arguments=arguments), self.assertRaises(ProtocolError):
                parse_tool_arguments({"arguments": arguments}, lambda args: True)
        with self.assertRaises(ProtocolError):
            parse_tool_arguments({"arguments": '{"unexpected":1}'}, lambda args: args == {})

    def test_json_unicode_and_slash_escaping_are_semantic(self):
        call = {"arguments": '{"path":"a\\/b","name":"\\u4e2d"}'}
        self.assertEqual(parse_tool_arguments(call, lambda args: set(args) == {"path", "name"}),
                         {"path": "a/b", "name": "中"})


if __name__ == "__main__":
    unittest.main(verbosity=2)

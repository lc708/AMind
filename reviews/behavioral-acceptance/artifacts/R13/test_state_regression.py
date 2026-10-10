from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from state_regression import (StateError, append_response, build_manual,
                              build_stateful, check_results, diagnose, mock_read,
                              pending_calls, run_demo)

TASK_PATH = Path(__file__).with_name('task.json')


class StateRegressionTests(unittest.TestCase):
    def setUp(self):
        self.task = json.loads(TASK_PATH.read_text())
        self.fixture = self.task['fixture']
        self.previous = self.fixture['previous_response']
        self.result = {'type': 'function_call_output', 'call_id': 'c1', 'output': 'invoice'}
        self.history = [self.fixture['next_request']['input'][0]]

    def test_original_fixture_reproduces_independent_faults(self):
        findings = diagnose(self.previous, self.fixture['next_request'])
        self.assertEqual({f['code'] for f in findings}, {
            'PHASE_CHANGED_OR_LOST', 'REPLAY_WITH_REFERENCE',
            'UNKNOWN_CALL_ID', 'MISSING_RESULT'})
        with self.assertRaisesRegex(StateError, 'UNKNOWN_CALL_ID'):
            check_results(self.previous, [self.fixture['next_request']['input'][2]])

    def test_stateful_contains_only_delta(self):
        request = build_stateful(self.previous, [self.result])
        self.assertEqual(request, {'previous_response_id': 'r1', 'input': [self.result]})
        self.assertEqual(diagnose(self.previous, request), [])

    def test_manual_replays_original_output_and_phase(self):
        request = build_manual(self.history, self.previous, [self.result])
        self.assertNotIn('previous_response_id', request)
        self.assertEqual(request['input'], self.history + self.previous['output'] + [self.result])
        self.assertEqual(request['input'][1]['phase'], 'commentary')
        self.assertEqual(diagnose(self.previous, request, prior_history=self.history), [])
        request['input'][1].pop('phase')
        self.assertIn('HISTORY_NOT_PRESERVED', {f['code'] for f in diagnose(
            self.previous, request, prior_history=self.history)})

    def test_does_not_assume_repeated_user_text_is_history(self):
        request = build_stateful(self.previous, [self.result], new_input=self.history)
        self.assertEqual(request['input'], [self.result] + self.history)
        self.assertEqual(request['input'][-1]['content'], 'Find invoice')

    def test_wrong_reference_detected(self):
        request = build_stateful(self.previous, [self.result])
        request['previous_response_id'] = 'other'
        self.assertEqual(diagnose(self.previous, request)[0]['code'], 'WRONG_RESPONSE_ID')

    def test_parallel_results_are_correlated_by_id_not_order(self):
        self.previous['output'].append({'type': 'function_call', 'call_id': 'c2', 'name': 'read', 'arguments': '{}'})
        second = dict(self.result, call_id='c2', output='second invoice')
        request = build_stateful(self.previous, [second, self.result])
        self.assertEqual([x['call_id'] for x in request['input']], ['c2', 'c1'])
        with self.assertRaisesRegex(StateError, 'MISSING_RESULTS: c2'):
            build_stateful(self.previous, [self.result])

    def test_duplicate_result_and_duplicate_call_rejected(self):
        with self.assertRaisesRegex(StateError, 'DUPLICATE_RESULT'):
            build_stateful(self.previous, [self.result, self.result])
        self.previous['output'].append(deepcopy(self.previous['output'][1]))
        with self.assertRaisesRegex(StateError, 'DUPLICATE_CALL_ID'):
            pending_calls(self.previous)

    def test_opaque_and_unknown_fields_survive_serialization(self):
        response = {'output': [self.fixture['later_compaction'], {
            'type': 'message', 'role': 'assistant', 'phase': 'final_answer',
            'content': 'Done', 'future_field': {'opaque': ['x', 1]}}]}
        output = append_response(self.history, response)
        roundtrip = json.loads(json.dumps(output))
        self.assertEqual(roundtrip[1:], response['output'])
        self.assertEqual(roundtrip[1]['encrypted_content'], 'opaque-2')
        self.assertEqual(roundtrip[2]['phase'], 'final_answer')
        self.assertEqual(roundtrip[2]['future_field'], {'opaque': ['x', 1]})

    def test_no_source_mutation_or_aliasing(self):
        before = deepcopy(self.task)
        manual = build_manual(self.history, self.previous, [self.result])
        manual['input'][1]['phase'] = 'changed'
        manual['input'][0]['content'] = 'changed'
        stateful = build_stateful(self.previous, [self.result])
        stateful['input'][0]['output'] = 'changed'
        self.assertEqual(self.task, before)
        self.assertEqual(self.result['output'], 'invoice')
        self.assertEqual(hashlib.sha256(TASK_PATH.read_bytes()).hexdigest(),
                         '7044074843610eb034c310af31c47396cfdfb6105a809e71eb881ce27df82ddc')

    def test_mock_binds_original_id_and_refuses_other_tools(self):
        call = self.previous['output'][1]
        self.assertEqual(mock_read(call, 'invoice'), self.result)
        with self.assertRaisesRegex(StateError, 'UNSUPPORTED_MOCK_CALL'):
            mock_read(dict(call, name='send_email'), 'invoice')
        with self.assertRaises(json.JSONDecodeError):
            mock_read(dict(call, arguments='{'), 'invoice')

    def test_complete_demo_runs_with_network_connection_blocked(self):
        with patch.object(socket, 'socket', side_effect=AssertionError('network forbidden')):
            report = run_demo(self.task)
        self.assertTrue(all(not issues for issues in report['after_findings'].values()))
        self.assertEqual(report['later_history_with_compaction'][-1], self.fixture['later_compaction'])


if __name__ == '__main__':
    unittest.main()

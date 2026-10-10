"""Held-out local failure contracts discovered during skill acceptance.

No model or external service calls. --skill-root can address a frozen old package.
These tests verify kernels, not whole-skill model behavior.
"""
import argparse
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ROOT = Path(__file__).resolve().parents[1]
loop = load_module('loop_probe', ROOT / 'skills/amind-engineering/scripts/tool_loop.py')
response = load_module('response_probe', ROOT / 'skills/amind-engineering/scripts/response_contract.py')
context = load_module('context_probe', ROOT / 'skills/amind-engineering/scripts/context_audit.py')


class HeldoutContracts(unittest.TestCase):
    def test_chain_audit_warns_on_phase_lost_replay_but_not_fresh_user_text(self):
        original = {'type': 'message', 'role': 'assistant', 'phase': 'commentary',
                    'content': 'Working'}
        first = {'state_owner': 'response_chain', 'request': {'input': []},
                 'response': {'id': 'r1', 'output': [original]}}
        replay = {key: value for key, value in original.items() if key != 'phase'}
        second = {'state_owner': 'response_chain', 'request': {
            'previous_response_id': 'r1', 'input': [replay]}}
        result = context.audit([first, second])
        findings = [item for item in result['findings']
                    if item['code'] == 'possible_phase_drift_replay']
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['severity'], 'warning')
        self.assertNotIn('Working', json.dumps(result))
        second['request']['input'] = [dict(replay, role='user')]
        self.assertEqual(context.audit([first, second])['findings'], [])

    def test_completed_with_incomplete_details_is_rejected_on_both_paths(self):
        body = {'status': 'completed', 'output': [],
                'incomplete_details': {'reason': 'max_output_tokens'}}
        with self.subTest(surface='response'):
            with self.assertRaises(ValueError):
                response.normalize(body)
        with self.subTest(surface='batch'):
            result = response.match_batch(['x'], [{'custom_id': 'x', 'response': {
                'status_code': 200, 'body': body}}])
            self.assertIn('x', result['errors'])

    def test_batch_completed_body_with_error_is_not_success(self):
        raw = {'custom_id': 'x', 'response': {'status_code': 200, 'body': {
            'status': 'completed', 'error': {'code': 'upstream_failure'},
            'usage': {'output_tokens': 17}}}}
        result = response.match_batch(['x'], [raw])
        self.assertIn('x', result['errors'])
        self.assertEqual(result['ordered'][0], raw)

    def test_contradictory_completed_error_is_not_accepted(self):
        with self.assertRaises(ValueError):
            response.normalize({'status': 'completed', 'output': [], 'error': {'code': 'failed'}})

    def test_interrupted_stream_preserves_raw_usage_evidence(self):
        events = [{'type': 'response.in_progress', 'response': {'usage': {'output_tokens': 17}}},
                  {'type': 'response.output_text.delta', 'delta': 'partial'}]
        result = response.terminal_stream(events)
        self.assertFalse(result['scorable_transport'])
        self.assertEqual(result.get('raw_events'), events)
        self.assertIsNone(result['usage'], 'partial usage evidence must not be advertised as a final bill')

    def test_legacy_remote_key_is_reused_for_pending_operation(self):
        effects = []
        request = {'task': 'job', 'name': 'charge', 'args': {}}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                def lost_receipt(key):
                    effects.append(key)
                    raise TimeoutError('remote succeeded, receipt lost')
                with self.assertRaises(TimeoutError):
                    ledger.perform('tenant', 'persisted-old-key', request, lost_receipt)
                tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None,
                        'handler': lambda arguments, key: effects.append(key), 'side_effect': True}
                with self.assertRaises(loop.ReconciliationRequired):
                    loop.run_loop(lambda unused: {'status': 'completed', 'output': [
                        {'type': 'function_call', 'call_id': 'c', 'name': 'charge', 'arguments': '{}'}]},
                        [], {'charge': tool}, 'tenant', 'job', ledger, lambda *x: None,
                        operation_key_for=lambda *scope: 'persisted-old-key')
                self.assertEqual(effects, ['persisted-old-key'])
            finally:
                ledger.close()

    def test_remote_key_scopes_tenant_even_when_task_and_call_ids_match(self):
        keys = []
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                for tenant in ('tenant-a', 'tenant-b'):
                    turns = iter([
                        {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'same-call', 'name': 'charge', 'arguments': '{"amount": 20}'}]},
                        {'status': 'completed', 'output': []},
                    ])
                    def handler(arguments, key):
                        keys.append(key)
                        return {'operation_id': key}
                    tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None, 'handler': handler, 'side_effect': True}
                    loop.run_loop(lambda request: next(turns), [], {'charge': tool}, tenant, 'same-task', ledger, lambda *x: None)
            finally:
                ledger.close()
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2, 'remote dedup keys must not alias across authenticated tenants')

    def test_cancellation_during_authorization_prevents_dispatch(self):
        cancelled = [False]
        effects = []
        def authorize(*unused):
            cancelled[0] = True
        def handler(arguments, key):
            effects.append(key)
            return 'charged'
        tool = {'schema': {'name': 'charge'}, 'validate': lambda x: None, 'handler': handler, 'side_effect': True}
        with tempfile.TemporaryDirectory() as tmp:
            ledger = loop.EffectLedger(str(Path(tmp) / 'ledger.db'))
            try:
                with self.assertRaisesRegex(RuntimeError, 'cancelled'):
                    loop.run_loop(lambda request: {'status': 'completed', 'output': [{'type': 'function_call', 'call_id': 'c', 'name': 'charge', 'arguments': '{}'}]}, [], {'charge': tool}, 't', 'job', ledger, authorize, cancelled=lambda: cancelled[0])
            finally:
                ledger.close()
        self.assertEqual(effects, [], 'no new effect after cancellation observed during authorization')

    def test_batch_http_success_does_not_hide_incomplete_body(self):
        raw = {'custom_id': 'x', 'response': {'status_code': 200, 'body': {'status': 'incomplete', 'usage': {'output_tokens': 17}}}}
        result = response.match_batch(['x'], [raw])
        self.assertIn('x', result['errors'])
        self.assertEqual(result['ordered'][0]['response']['body']['usage'], {'output_tokens': 17})

    def test_text_projection_distinguishes_commentary_and_final(self):
        output = [
            {'type': 'reasoning', 'encrypted_content': 'opaque'},
            {'type': 'message', 'role': 'assistant', 'phase': 'commentary', 'content': [{'type': 'output_text', 'text': 'Working'}]},
            {'type': 'function_call', 'call_id': 'c', 'name': 'lookup', 'arguments': '{}'},
        ]
        result = response.normalize({'status': 'completed', 'output': output})
        self.assertEqual(result.get('final_text'), '')
        self.assertEqual(result.get('commentary_text'), 'Working')
        self.assertFalse(result.get('answer_complete'))
        self.assertEqual(result['output_items'], output)
        final = response.normalize({'status': 'completed', 'output': [{'type': 'message', 'role': 'assistant', 'phase': 'final_answer', 'content': [{'type': 'output_text', 'text': 'Ready'}]}]})
        self.assertEqual(final.get('final_text'), 'Ready')
        self.assertTrue(final.get('answer_complete'))


class RecordingResult(unittest.TextTestResult):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.records = []
    def addSuccess(self, test):
        super().addSuccess(test)
        self.records.append({'test': test.id(), 'status': 'passed'})
    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.records.append({'test': test.id(), 'status': 'failed', 'detail': self._exc_info_to_string(err, test)})
    def addError(self, test, err):
        super().addError(test, err)
        self.records.append({'test': test.id(), 'status': 'error', 'detail': self._exc_info_to_string(err, test)})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skill-root', type=Path, default=ROOT / 'skills/amind-engineering')
    parser.add_argument('--json', type=Path)
    args = parser.parse_args()
    loop = load_module('loop_probe', args.skill_root / 'scripts/tool_loop.py')
    response = load_module('response_probe', args.skill_root / 'scripts/response_contract.py')
    context = load_module('context_probe', args.skill_root / 'scripts/context_audit.py')
    result = unittest.TextTestRunner(verbosity=2, resultclass=RecordingResult).run(unittest.defaultTestLoader.loadTestsFromTestCase(HeldoutContracts))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({'skill_root': str(args.skill_root.resolve()), 'tests_run': result.testsRun,
                                        'tests': result.records, 'passed': result.wasSuccessful(),
                                        'failures': [{'test': str(test), 'detail': detail} for test, detail in result.failures + result.errors],
                                        'scope': 'offline kernel contracts, not agent behavior'}, ensure_ascii=False, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)

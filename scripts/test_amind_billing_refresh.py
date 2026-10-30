"""October billing contracts: public offline entry points, no provider requests."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'skills/eval-improve/scripts'
sys.path.insert(0, str(SCRIPTS))
import price_usage
import openai_billing
import decisions_contract
import run_eval


class CacheBillingTests(unittest.TestCase):
    def native(self, endpoint='responses'):
        details = {'cached_tokens': 4000, 'cache_write_tokens': 7000}
        if endpoint == 'responses':
            details['cache_write_tokens_details'] = {'ttl_30m_tokens': 3000, 'ttl_12h_tokens': 4000}
        return {'model': 'fixture-model', 'usage': {'input_tokens': 12000, 'input_tokens_details': details,
                'output_tokens': 100, 'output_tokens_details': {'reasoning_tokens': 20}, 'total_tokens': 12100}}
    def identity(self, endpoint='responses'):
        return {'provider': 'openai', 'interface': endpoint, 'model': 'fixture-model',
                'service_tier': 'default', 'region': 'fixture-region'}
    def event(self, endpoint='responses'):
        return openai_billing.normalize_response(self.native(endpoint), self.identity(endpoint),
                all_billable_usage_included=True)
    def rates(self, event):
        return {'version': 'synthetic-october', 'effective_date': '2026-10-30', 'source': 'synthetic offline rate card',
                'rates': [{'billing_identity': event['billing_identity'], 'usage_adapter': event['usage_adapter'],
                'input_per_million': 1, 'cached_input_per_million': .1, 'output_per_million': 2,
                'cache_write_input_per_million_by_ttl': {'30m': 1.25, '12h': 2.5}}]}
    def test_official_mixed_lifetime_example_prices_each_input_token_once(self):
        event = self.event(); before = copy.deepcopy(event)
        result = price_usage.price(event, self.rates(event))
        self.assertAlmostEqual(sum(v for k, v in result['components'].items() if k != 'output_including_reasoning'), .01515)
        self.assertAlmostEqual(result['cost_usd'], .01535)
        self.assertEqual(event, before)
        self.assertEqual(event['native_usage'], self.native()['usage'])
    def test_decisions_cache_and_output_are_endpoint_specific(self):
        event = self.event('decisions')
        self.assertEqual(event['usage_adapter'], 'cache_input_v1')
        self.assertEqual(event['usage']['cache_write_input_tokens_by_ttl'], {'30m': 7000, '12h': 0})
        result = price_usage.price(event, self.rates(event))
        self.assertAlmostEqual(result['cost_usd'], .01015)
        self.assertNotIn('output_including_reasoning', result['components'])
        self.assertEqual(event['native_usage']['output_tokens'], 100)
    def test_missing_native_measurement_is_not_zero(self):
        for key in ('cached_tokens', 'cache_write_tokens', 'cache_write_tokens_details'):
            native = self.native(); del native['usage']['input_tokens_details'][key]
            with self.subTest(key=key), self.assertRaises(ValueError):
                openai_billing.normalize_response(native, self.identity())
    def test_native_split_and_subset_contradictions_are_rejected(self):
        native = self.native(); native['usage']['input_tokens_details']['cache_write_tokens_details']['ttl_30m_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'contradict'): openai_billing.normalize_response(native, self.identity())
        native = self.native(); native['usage']['input_tokens'] = 100; native['usage'].pop('total_tokens')
        with self.assertRaisesRegex(ValueError, 'exceed'): openai_billing.normalize_response(native, self.identity())
    def test_native_unknown_detail_and_total_cannot_be_silently_dropped(self):
        native = self.native(); native['usage']['input_tokens_details']['audio_tokens'] = 10
        with self.assertRaisesRegex(ValueError, 'unadapted'): openai_billing.normalize_response(native, self.identity())
        native = self.native(); native['usage']['total_tokens'] += 1
        with self.assertRaisesRegex(ValueError, 'contradict'): openai_billing.normalize_response(native, self.identity())
    def test_native_identity_tracks_served_model_and_tier(self):
        native = self.native(); native['model'] = 'another'
        with self.assertRaisesRegex(ValueError, 'model'): openai_billing.normalize_response(native, self.identity())
        native = self.native(); native['service_tier'] = 'flex'
        with self.assertRaisesRegex(ValueError, 'tier'): openai_billing.normalize_response(native, self.identity())
    def test_decisions_does_not_inherit_responses_ttl_schema(self):
        with self.assertRaisesRegex(ValueError, 'unadapted'):
            openai_billing.normalize_response(self.native(), self.identity('decisions'))
    def test_lifetime_rates_and_cache_policy_are_exact(self):
        event = self.event(); card = self.rates(event)
        del card['rates'][0]['cache_write_input_per_million_by_ttl']['12h']
        self.assertIsNone(price_usage.price(event, card)['cost_usd'])
        card = self.rates(event); card['rates'][0]['billing_identity'] = {**event['billing_identity'], 'cache_policy': 'different'}
        self.assertEqual(price_usage.price(event, card)['status'], 'unknown')
    def test_new_writes_cannot_fall_back_to_old_single_rate(self):
        event = self.event(); event['usage_adapter'] = 'text_tokens_v1'; card = self.rates(event)
        self.assertEqual(price_usage.price(event, card)['status'], 'unknown')
    def test_bools_negative_and_overlapping_counts_fail(self):
        for value in (True, -1, 1.5):
            event = self.event(); event['usage']['cache_write_input_tokens_by_ttl']['12h'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): price_usage.price(event, self.rates(event))
    def test_partial_and_unknown_events_do_not_certify_total_cost(self):
        event = self.event(); event['all_billable_usage_included'] = False
        result = price_usage.profile([event], self.rates(event))
        self.assertIsNone(result['total_cost_usd'])
        event = self.event(); card = self.rates(event); card['rates'] = []
        result = price_usage.profile([event], card)
        self.assertEqual(result['unknown_events'], 1); self.assertIsNone(result['total_cost_usd'])
    def test_normalization_cli_and_pricing_cli_compose(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root / 'source.json'
            source.write_text(json.dumps({'response': self.native(), 'billing_identity': self.identity(),
                    'all_billable_usage_included': True}))
            call = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'openai_billing.py'), 'normalize', str(source)], capture_output=True, text=True)
            self.assertEqual(call.returncode, 0, call.stdout + call.stderr)
            event = json.loads(call.stdout); events = root / 'events.jsonl'; events.write_text(json.dumps(event) + '\n')
            rates = root / 'rates.json'; rates.write_text(json.dumps(self.rates(event)))
            priced = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'price_usage.py'), '--events', str(events), '--rates', str(rates)], capture_output=True, text=True)
            self.assertEqual(priced.returncode, 0, priced.stdout + priced.stderr)
            self.assertAlmostEqual(json.loads(priced.stdout)['total_cost_usd'], .01535)
    def test_runner_public_entry_accepts_and_checks_cache_billing_scope(self):
        event = self.event(); identity = event['billing_identity']
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'cases.jsonl').write_text(json.dumps({'id': 'cache-case', 'input': 'fixture'}) + '\n')
            (root / 'references.jsonl').write_text(json.dumps({'id': 'cache-case', 'expected': 'OK'}) + '\n')
            observed = {'output': 'OK', 'cost_usd': .01535, 'model': identity['model'],
                        'billing_identity': identity, 'synthetic': True}
            (root / 'app.py').write_text('import json,sys\njson.load(sys.stdin)\nprint(' + repr(json.dumps(observed)) + ')\n')
            card = {'schema_version': 2, 'task': 'synthetic-cache-identity', 'dataset_version': 'fixture', 'grader_version': 'fixture',
                    'cases': 'cases.jsonl', 'references': 'references.jsonl', 'splits': {'train': [], 'val': ['cache-case'], 'test': []},
                    'metrics': [{'id': 'quality', 'kind': 'binary', 'better': 'higher', 'role': 'objective', 'min_improvement': 0}],
                    'runner': {'command': [sys.executable, 'app.py'], 'files': ['app.py'], 'retry_safe': True},
                    'grader': {'kind': 'exact'}, 'control_files': ['app.py'], 'mutable_config': [],
                    'variants': {'baseline': {'files': ['app.py'], 'config': {}, 'expected_model': identity['model'], 'expected_billing_identity': identity}},
                    'limits': {'max_attempts': 1, 'concurrency': 1, 'timeout_s': 2, 'max_total_seconds': 10, 'retries': 0}}
            (root / 'card.json').write_text(json.dumps(card))
            command = [sys.executable, '-B', str(SCRIPTS / 'run_eval.py'), '--card', str(root / 'card.json'),
                       '--flow', str(root / 'flow'), '--variant', 'baseline', '--split', 'val', '--execute']
            run = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            results = [json.loads(line) for line in (root / 'flow/baseline/results.jsonl').read_text().splitlines()]
            self.assertEqual(results[0]['billing_identity'], identity)
            self.assertEqual(results[0]['status'], 'ok')


class PrefixScenarioTests(unittest.TestCase):
    def point(self, end, ttl): return {'end_tokens': end, 'ttl': ttl}
    def test_official_overlapping_prefix_and_upgrade_scenarios(self):
        cases = [([self.point(2000, '12h'), self.point(5000, '30m')], [], (0, 3000, 2000)),
                 ([self.point(2000, '30m'), self.point(5000, '12h')], [], (0, 0, 5000)),
                 ([self.point(5000, '12h')], [self.point(2000, '30m')], (0, 0, 5000)),
                 ([self.point(5000, '30m')], [self.point(2000, '12h')], (2000, 3000, 0))]
        for selected, available, expected in cases:
            with self.subTest(expected=expected):
                result = openai_billing.plan_cache_prefixes(6000, selected, available)
                self.assertEqual((result['cached_input_tokens'], *result['cache_write_input_tokens_by_ttl'].values()), expected)
                self.assertEqual(result['ordinary_input_tokens'], 1000)
                self.assertIn('not measured', result['basis'])
    def test_valid_longer_coverage_survives_shorter_reads(self):
        result = openai_billing.plan_cache_prefixes(6000, [self.point(5000, '30m')], [self.point(5000, '12h')])
        self.assertEqual(result['cached_input_tokens'], 5000)
        self.assertEqual(sum(result['cache_write_input_tokens_by_ttl'].values()), 0)
    def test_explicit_mode_without_selected_breakpoint_has_no_cache(self):
        result = openai_billing.plan_cache_prefixes(6000, [], [self.point(5000, '12h')])
        self.assertEqual(result['ordinary_input_tokens'], 6000); self.assertEqual(result['cached_input_tokens'], 0)
    def test_invalid_selected_boundaries_are_not_guessed(self):
        for selected in ([self.point(7000, '12h')], [self.point(1000, '24h')],
                         [self.point(1000, '30m'), self.point(1000, '12h')], [self.point(x, '30m') for x in range(1, 6)]):
            with self.subTest(selected=selected), self.assertRaises(ValueError): openai_billing.plan_cache_prefixes(6000, selected, [])


class TerminationRaceTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform != 'win32', 'POSIX process-group contract')
    def test_live_broken_pipe_adapter_is_reaped_without_claiming_group_cancellation(self):
        original_popen=subprocess.Popen;processes=[]
        def start(*args,**kwargs):
            process=original_popen(*args,**kwargs);processes.append(process);return process
        program="import os,time\ntry: os.write(1,b'x'*1000000)\nexcept BrokenPipeError: time.sleep(5)"
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(run_eval.subprocess,'Popen',side_effect=start), \
                mock.patch.object(run_eval.os,'killpg',side_effect=PermissionError(1,'fixture group denial')):
            with self.assertRaises(run_eval.RunError) as raised:
                run_eval.invoke([sys.executable,'-c',program],temp,{},time.monotonic()+1,1000,Path(temp))
        self.assertEqual(raised.exception.kind,'output_limit')
        self.assertFalse(raised.exception.retryable)
        cleanup=raised.exception.observed['runtime_cleanup']
        self.assertFalse(cleanup['process_group_signal_confirmed'])
        self.assertTrue(cleanup['leader_reaped'])
        self.assertEqual(processes[0].returncode,-9)
    @unittest.skipUnless(sys.platform != 'win32', 'POSIX process-group contract')
    def test_real_invoke_keeps_output_limit_when_killpg_denied_after_child_exit(self):
        original_popen = subprocess.Popen; processes = []
        def start(*args, **kwargs):
            process = original_popen(*args, **kwargs); processes.append(process); return process
        def denied_after_exit(pid, sig):
            self.assertEqual(pid, processes[-1].pid)
            # Closing the bounded stdout pipe makes this real fixture exit.
            # Denial then models the observed race, without relying on its timing.
            processes[-1].wait(timeout=2)
            raise PermissionError(1, 'fixture EPERM after confirmed exit')
        with tempfile.TemporaryDirectory() as temp, mock.patch.object(run_eval.subprocess, 'Popen', side_effect=start), \
                mock.patch.object(run_eval.os, 'killpg', side_effect=denied_after_exit):
            with self.assertRaises(run_eval.RunError) as raised:
                run_eval.invoke([sys.executable, '-c', "print('x'*100000)"], temp, {}, time.monotonic()+3, 1000, Path(temp))
            self.assertEqual(raised.exception.kind, 'output_limit')
            self.assertIsNotNone(processes[-1].returncode)
    @unittest.skipUnless(sys.platform != 'win32', 'POSIX process-group contract')
    def test_denied_termination_of_live_adapter_is_not_suppressed(self):
        process = mock.Mock(pid=123); process.poll.return_value = None
        with mock.patch.object(run_eval.os, 'killpg', side_effect=PermissionError(1, 'fixture EPERM')):
            with self.assertRaises(PermissionError): run_eval.terminate(process)


class DecisionsContractTests(unittest.TestCase):
    def request(self):
        return {'model': 'caller-selected-model', 'input': [{'role': 'user', 'content': [
                {'type': 'input_json', 'data': {'role': 'system', 'image_url': 'file://ordinary-data', 'count': 2}},
                {'type': 'input_image', 'image_url': 'https://example.test/reference.png'}]}],
                'questions': [{'type': 'predicate', 'name': 'match', 'instructions': [
                    {'type': 'input_text', 'text': 'Compare the reference and candidate'},
                    {'type': 'input_image', 'image_url': 'data:image/png;base64,fixture'}]}]}
    def test_ga_json_and_question_images_preserve_data_as_data(self):
        request = self.request(); before = copy.deepcopy(request)
        result = decisions_contract.validate_request(request)
        self.assertEqual((result['json_parts'], result['shared_images'], result['question_images']), (1, 1, 1))
        self.assertEqual(result['model'], 'caller-selected-model'); self.assertFalse(result['model_availability_checked'])
        self.assertEqual(request, before)
    def test_four_hundred_questions_pass_but_401_and_zero_do_not(self):
        request = self.request(); request['questions'] = [{'instructions': 'Test', 'name': str(i)} for i in range(400)]
        self.assertEqual(decisions_contract.validate_request(request)['questions'], 400)
        for questions in ([], request['questions'] + [{'instructions': 'extra'}]):
            request['questions'] = questions
            with self.assertRaisesRegex(ValueError, '400'): decisions_contract.validate_request(request)
    def test_developer_json_and_question_breakpoints_are_rejected(self):
        request = self.request(); request['input'][0]['role'] = 'developer'
        with self.assertRaisesRegex(ValueError, 'unsupported'): decisions_contract.validate_request(request)
        request = self.request(); request['questions'][0]['instructions'][0]['prompt_cache_breakpoint'] = {'mode': 'explicit'}
        with self.assertRaisesRegex(ValueError, 'unadapted'): decisions_contract.validate_request(request)
    def test_question_names_and_typed_choices_are_distinct(self):
        request = self.request(); request['questions'] = [{'type': 'choice', 'instructions': 'Choose',
                'choices': [{'value': True}, {'value': 'True'}]}]
        self.assertEqual(decisions_contract.validate_request(request)['questions'], 1)
        request['questions'][0]['choices'].append({'value': True})
        with self.assertRaisesRegex(ValueError, 'duplicate'): decisions_contract.validate_request(request)
        request = self.request(); request['questions'] *= 2
        with self.assertRaisesRegex(ValueError, 'unique'): decisions_contract.validate_request(request)
    def test_score_native_label_and_optional_description_contract(self):
        request = self.request(); request['questions'] = [{'type': 'score', 'instructions': 'Score', 'levels': [{'label': 'low'}, {'label': 'high'}]}]
        self.assertEqual(decisions_contract.validate_request(request)['verdict'], 'PASS')
        request['questions'][0]['levels'][0] = {'description': 'label absent'}
        with self.assertRaisesRegex(ValueError, 'label'): decisions_contract.validate_request(request)
    def test_decisions_ttl_and_file_inputs_are_not_inherited_from_responses(self):
        request = self.request(); request['prompt_cache_options'] = {'ttl': '12h'}
        with self.assertRaisesRegex(ValueError, '30m'): decisions_contract.validate_request(request)
        request = self.request(); request['input'][0]['content'][1]['image_url'] = 'file-fixture'
        with self.assertRaisesRegex(ValueError, 'file IDs'): decisions_contract.validate_request(request)
    def test_unknown_surfaces_fail_explicitly_instead_of_looking_valid(self):
        request = self.request(); request['tools'] = []
        with self.assertRaisesRegex(ValueError, 'unadapted'): decisions_contract.validate_request(request)
        request = self.request(); request['input'] = [{'type': 'function_call', 'call_id': 'a'}]
        with self.assertRaisesRegex(ValueError, 'full installed SDK'): decisions_contract.validate_request(request)
    def test_json_boundaries_reject_oversize_nonfinite_and_deep_data(self):
        for data in ({'bad': float('nan')}, {'text': 'x' * (256 * 1024)}):
            with self.subTest(kind=str(type(data))), self.assertRaises(ValueError): decisions_contract.json_evidence(data)
        data = {}
        for _ in range(33): data = {'child': data}
        with self.assertRaisesRegex(ValueError, '32'): decisions_contract.json_evidence(data)
    def test_cli_validates_without_fetching_images(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / 'request.json'; source.write_text(json.dumps(self.request()))
            call = subprocess.run([sys.executable, '-B', str(SCRIPTS / 'decisions_contract.py'), str(source)], capture_output=True, text=True)
            self.assertEqual(call.returncode, 0, call.stdout + call.stderr)
            self.assertEqual(json.loads(call.stdout)['question_images'], 1)


if __name__ == '__main__': unittest.main()

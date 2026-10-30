"""October method contracts exercised through normalized evidence and the public CLI."""
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/amind-engineering/scripts/method_diagnostics.py'
spec = importlib.util.spec_from_file_location('amind_october_methods', SCRIPT)
methods = importlib.util.module_from_spec(spec)
spec.loader.exec_module(methods)
HASH = 'a' * 64


class OctoberMethodContracts(unittest.TestCase):
    def component(self, identity, **overrides):
        row = {'id': identity, 'role': 'domain', 'independent_verification': False,
               'separate_permissions': False, 'parallel_work': False, 'context_pressure_observed': False,
               'talks_to_user': False, 'coupling_observed': True, 'deterministic': False,
               'evidence': 'captured production traces'}
        row.update(overrides)
        return row

    def comparison(self):
        base = [{'case_id': 'delivery', 'success': True, 'constraint_violations': 0, 'cost_usd': 2, 'latency_ms': 100},
                {'case_id': 'refund', 'success': False, 'constraint_violations': 0, 'cost_usd': 1, 'latency_ms': 100}]
        return {'dataset_id': 'frozen-v1', 'grader_id': 'rubric-v1', 'baseline_id': 'multi', 'candidate_id': 'folded',
                'required_case_ids': ['delivery', 'refund'], 'required_path_ids': ['order-shipping', 'refund'],
                'baseline': {'cases': base, 'covered_path_ids': ['order-shipping', 'refund'], 'evidence': 'baseline.jsonl'},
                'candidate': {'cases': copy.deepcopy(base), 'covered_path_ids': ['order-shipping', 'refund'], 'evidence': 'candidate.jsonl'}}

    def test_architecture_keeps_isolation_and_offers_each_migration_without_executing_it(self):
        components = [self.component('router', role='router'), self.component('domain', shares_context_with=['router']),
                      self.component('verifier', independent_verification=True, talks_to_user=True),
                      self.component('parallel', parallel_work=True), self.component('lookup', deterministic=True)]
        result = methods.architecture({'components': components})
        self.assertEqual([r['suggested_action'] for r in result['suggestions']], ['fold', 'merge', 'keep', 'as-tool', 'as-tool'])
        self.assertEqual(result['comparison']['status'], 'not_measured')

    def test_architecture_unknown_structural_evidence_does_not_select_fold(self):
        component = self.component('router', role='router')
        del component['parallel_work']
        result = methods.architecture({'components': [component]})
        self.assertEqual(result['suggestions'][0]['suggested_action'], 'investigate')

    def test_equal_average_success_does_not_hide_a_previously_passing_task_regression(self):
        comparison = self.comparison()
        comparison['candidate']['cases'][0]['success'] = False
        comparison['candidate']['cases'][1]['success'] = True
        result = methods.architecture({'comparison': comparison})['comparison']
        self.assertEqual(result['status'], 'regressed')
        self.assertEqual(result['regressed_case_ids'], ['delivery'])
        self.assertEqual(result['improved_case_ids'], ['refund'])

    def test_architecture_requires_all_cases_and_production_chains_without_dropping_missing_data(self):
        comparison = self.comparison()
        comparison['candidate']['cases'].pop()
        comparison['candidate']['covered_path_ids'] = ['refund']
        result = methods.architecture({'comparison': comparison})['comparison']
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['coverage'], .5)
        self.assertEqual(result['missing_cases']['candidate'], ['refund'])
        self.assertEqual(result['missing_paths']['candidate'], ['order-shipping'])
        self.assertIsNone(result['mean_candidate_minus_baseline']['cost_usd'])

    def test_architecture_unknown_cost_is_not_zero_and_violation_increase_is_reported(self):
        comparison = self.comparison()
        comparison['candidate']['cases'][0]['cost_usd'] = None
        comparison['candidate']['cases'][1]['constraint_violations'] = 1
        result = methods.architecture({'comparison': comparison})['comparison']
        self.assertEqual(result['status'], 'regressed')
        self.assertIsNone(result['mean_candidate_minus_baseline']['cost_usd'])
        self.assertEqual(result['increased_violation_case_ids'], ['refund'])

    def test_architecture_rejects_duplicate_cases_nonfinite_cost_and_changed_identity(self):
        for mutate in (lambda c: c['candidate']['cases'].append(c['candidate']['cases'][0]),
                       lambda c: c['candidate']['cases'][0].update(cost_usd=float('nan')),
                       lambda c: c.update(candidate_id='multi'),
                       lambda c: c['candidate'].update(covered_path_ids=['undeclared'])):
            comparison = self.comparison()
            mutate(comparison)
            with self.subTest(comparison=comparison), self.assertRaises(ValueError):
                methods.architecture({'comparison': comparison})

    def round(self, findings=None, **overrides):
        row = {'patch_sha256': HASH, 'changed_paths': ['gateway.py'], 'checked_paths': ['gateway.py'],
               'checks': [{'id': 'regression', 'status': 'passed', 'patch_sha256': HASH, 'evidence': 'test-receipt.json'}],
               'findings': findings or []}
        row.update(overrides)
        return row

    def finding(self, **overrides):
        row = {'key': 'authorization-boundary', 'path': 'gateway.py', 'contract': 'tenant identity outside model input',
               'blocking': True, 'status': 'open', 'evidence': 'trace.json:tool-dispatch'}
        row.update(overrides)
        return row

    def test_missing_finding_in_later_review_does_not_silently_close_it(self):
        result = methods.review({'max_rounds': 3, 'required_check_ids': ['regression'],
                                 'rounds': [self.round([self.finding()]), self.round()]})
        self.assertEqual(result['status'], 'needs_follow_up')
        self.assertEqual(result['open_blocking_finding_keys'], ['authorization-boundary'])

    def test_duplicate_finding_is_not_new_and_explicit_verified_resolution_can_converge(self):
        result = methods.review({'max_rounds': 3, 'required_check_ids': ['regression'],
                                 'rounds': [self.round([self.finding()]), self.round([self.finding()]),
                                            self.round([self.finding(status='resolved', evidence='regression receipt')])]})
        self.assertEqual(result['status'], 'converged')
        self.assertEqual(result['rounds'][1]['new_finding_keys'], [])

    def test_review_stops_at_limit_and_never_turns_budget_exhaustion_into_success(self):
        result = methods.review({'max_rounds': 1, 'required_check_ids': ['regression'],
                                 'rounds': [self.round([self.finding()])]})
        self.assertEqual(result['status'], 'round_limit')
        with self.assertRaises(ValueError):
            methods.review({'max_rounds': 1, 'required_check_ids': ['regression'], 'rounds': [self.round(), self.round()]})

    def test_review_different_patch_checks_missing_coverage_and_finding_key_collision(self):
        capture = {'max_rounds': 2, 'required_check_ids': ['regression'], 'rounds': [self.round(checked_paths=[])]}
        self.assertNotEqual(methods.review(capture)['status'], 'converged')
        capture['rounds'][0]['checks'][0]['patch_sha256'] = 'b' * 64
        with self.assertRaises(ValueError): methods.review(capture)
        capture['rounds'] = [self.round([self.finding()]), self.round([self.finding(contract='another contract')])]
        with self.assertRaises(ValueError): methods.review(capture)

    def decision(self, identity='a', **overrides):
        row = {'case_id': identity, 'agent_preference': 'yield', 'final_choice': 'yield', 'reviewer_id': 'analyst-1',
               'preference_assignment': 'randomized', 'balanced_alternatives': True,
               'prior_choice': 'cost', 'prior_recorded_before_advice': True, 'evidence': 'blinded-capture.json'}
        row.update(overrides)
        return row

    def test_approval_and_preference_following_do_not_certify_independent_judgment(self):
        result = methods.oversight({'required_case_ids': ['a', 'b'], 'observations': [self.decision(), self.decision('b')]})
        self.assertEqual(result['status'], 'observed')
        self.assertEqual(result['followed_agent_rate'], 1)
        self.assertEqual(result['distinct_reviewers'], 1)
        self.assertEqual(result['switched_toward_agent_count'], 2)
        self.assertEqual(result['judgment_independence'], 'not_established')

    def test_oversight_missing_population_and_missing_prior_are_not_zero_effect(self):
        result = methods.oversight({'required_case_ids': ['a', 'b'],
                                    'observations': [self.decision(prior_choice=None, prior_recorded_before_advice=False)]})
        self.assertEqual(result['status'], 'inconclusive')
        self.assertEqual(result['prior_disagreement_count'], 0)
        self.assertEqual(result['missing_evidence_ids'], ['b'])
        with self.assertRaises(ValueError):
            methods.oversight({'required_case_ids': ['a'], 'observations': [self.decision(prior_choice=None)]})

    def handoff(self):
        action = {'action_sha256': HASH, 'resource_version': 'approved-files-v1',
                  'authority_origin': 'trusted_control_plane', 'evidence': 'signed-approval-receipt'}
        return {'approval': action, 'dispatch': dict(action), 'required_handoff_ids': ['summary'],
                'handoffs': [{'id': 'summary', 'kind': 'compaction', 'monitor_applied': True,
                              'claims_authorization': False, 'authority_origin': 'none', 'evidence': 'monitor.json'}]}

    def test_handoff_flags_summary_authorization_laundering_and_changed_approved_execution(self):
        capture = self.handoff()
        capture['handoffs'][0].update(claims_authorization=True, authority_origin='untrusted_content')
        capture['dispatch'].update(action_sha256='b' * 64, resource_version='files-v2')
        result = methods.handoff(capture)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('summary:untrusted_authorization_claim', result['findings'])
        self.assertIn('action_changed_after_approval', result['findings'])
        self.assertIn('resource_changed_after_approval', result['findings'])

    def test_handoff_missing_monitor_or_shared_file_mutation_never_passes(self):
        capture = self.handoff()
        capture['handoffs'][0]['monitor_applied'] = False
        self.assertEqual(methods.handoff(capture)['status'], 'inconclusive')
        capture['handoffs'][0].update(kind='shared_file', monitor_applied=True,
                                       expected_sha256=HASH, observed_sha256='b' * 64)
        self.assertEqual(methods.handoff(capture)['status'], 'failed')
        capture['handoffs'] = []
        self.assertEqual(methods.handoff(capture)['unmeasured'], ['summary'])

    def test_claude_migration_is_version_scoped_and_accepts_allowed_nested_documents(self):
        capture = {'provider': 'anthropic', 'api_version': '2026-10-21', 'request': {'temperature': 1,
                   'messages': [{'role': 'assistant', 'content': [{'type': 'document'},
                                {'type': 'tool_result', 'content': [{'type': 'document'}]}]},
                                {'role': 'user', 'content': [{'type': 'search_result', 'content': [
                                    {'type': 'text', 'text': 'source', 'citations': [{'location': 1}]}]}]}]}}
        result = methods.claude_api(capture)
        self.assertEqual(result['status'], 'needs_migration')
        self.assertEqual(len(result['findings']), 3)
        capture['api_version'] = '2023-06-01'
        self.assertEqual(methods.claude_api(capture)['status'], 'out_of_scope')
        capture.update(provider='openai', api_version='2026-10-21')
        self.assertEqual(methods.claude_api(capture)['status'], 'out_of_scope')

    def test_claude_empty_user_citations_and_document_citation_settings_are_preserved(self):
        capture = {'provider': 'anthropic', 'api_version': '2026-10-21', 'request': {'messages': [
            {'role': 'user', 'content': [{'type': 'text', 'text': 'question', 'citations': []},
                                       {'type': 'document', 'citations': {'enabled': True}}]}]}}
        before = copy.deepcopy(capture)
        self.assertEqual(methods.claude_api(capture)['status'], 'checked')
        self.assertEqual(capture, before)

    def test_public_cli_reads_capture_without_writing_and_returns_nonzero_for_invalid_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'capture.json'
            path.write_text(json.dumps(self.handoff()))
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'handoff', str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)['status'], 'observed')
            self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()), ['capture.json'])
            path.write_text('{}')
            result = subprocess.run([sys.executable, '-B', str(SCRIPT), 'handoff', str(path)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 2)
            self.assertNotIn('Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()

import hashlib
import json
from pathlib import Path
import unittest

from regression import ROOT, PREFIX, consume_response, validate_trace, run_probes


class PromptRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.task_bytes = (ROOT / 'task.json').read_bytes()
        cls.task = json.loads(cls.task_bytes)
        cls.original = cls.task['fixture']['prompt']
        cls.step1 = (ROOT / '01_tools_corrected.txt').read_text().removesuffix('\n')
        cls.candidate = (ROOT / 'candidate_prompt.txt').read_text().removesuffix('\n')

    def test_original_input_unchanged(self):
        manifest = json.loads((ROOT / 'input_manifest.json').read_text())
        self.assertEqual(hashlib.sha256(self.task_bytes).hexdigest(), manifest['task_sha256'])
        self.assertEqual((ROOT / 'original_prompt.txt').read_text(), self.original + '\n')
        self.assertEqual(manifest['target'], 'current configured model, preserve provider')
        self.assertEqual(manifest['actual_tools'], ['lookup_payment', 'charge_once'])

    def test_first_patch_only_removes_obsolete_claim(self):
        self.assertEqual(self.step1, self.original.replace('You have no tools. ', '', 1))
        self.assertIn('output exactly three sentences.', self.step1)

    def test_second_patch_only_removes_sentence_rule(self):
        self.assertEqual(self.candidate, self.step1.replace(' and output exactly three sentences.', '', 1))

    def test_incident_constraints_stay_verbatim_in_all_versions(self):
        rules = 'IMPORTANT: always check payment status before retrying. NEVER charge twice.'
        for prompt in [self.original, self.step1, self.candidate]:
            self.assertTrue(prompt.startswith(rules))
            self.assertIn('Begin every answer with RESULT:', prompt)

    def test_obsolete_fact_is_contradicted_by_fixture(self):
        self.assertTrue(self.task['fixture']['actual_tools'])
        self.assertIn('You have no tools.', self.original)
        self.assertNotIn('You have no tools.', self.candidate)

    def test_no_tool_contract_or_provider_invented_in_candidate(self):
        for addition in ['lookup_payment', 'charge_once', 'claude', 'anthropic', 'idempotency']:
            self.assertNotIn(addition, self.candidate)


class ConsumerRegression(unittest.TestCase):
    def test_exact_legacy_slice(self):
        self.assertEqual(len(PREFIX), 7)
        for body in [' Payment already completed.', '已完成支付。', '\nPayment pending.',
                     'One. Two. Three.', 'One. Two. Three. Four.']:
            with self.subTest(body=body):
                self.assertEqual(consume_response(PREFIX + body), body)

    def test_reject_prefix_breaks(self):
        for response in ['result: paid', ' RESULT: paid', '\nRESULT: paid',
                         '```RESULT: paid```', 'RESULT paid', 'RESULT：paid']:
            with self.subTest(response=response):
                with self.assertRaisesRegex(ValueError, 'invalid_result_prefix'):
                    consume_response(response)

    def test_reject_empty_response(self):
        for response in ['RESULT:', 'RESULT: \n']:
            with self.assertRaisesRegex(ValueError, 'empty_response'):
                consume_response(response)


class TraceRegression(unittest.TestCase):
    def test_fixed_safe_and_unsafe_traces(self):
        cases = json.loads((ROOT / 'traces.json').read_text())
        for case in cases:
            with self.subTest(case=case['id']):
                self.assertEqual(validate_trace(case['events'], case['response']), case['errors'])

    def test_oracle_rejects_removed_lookup(self):
        # Mutate a safe trace, not the acceptance criterion, to verify the oracle.
        events = [{'tool': 'charge_once', 'payment_id': 'p1', 'status': 'paid'}]
        self.assertIn('charge_without_fresh_unpaid_lookup', validate_trace(events, 'RESULT: Paid.'))

    def test_report_states_evidence_limits(self):
        report = run_probes()
        self.assertEqual(report['model_calls'], 0)
        self.assertFalse(report['provider_changed'])
        self.assertTrue(report['all_trace_expectations_met'])
        self.assertTrue(report['variants']['original_prompt.txt']['contradicts_actual_tools'])
        self.assertFalse(report['variants']['candidate_prompt.txt']['contradicts_actual_tools'])


if __name__ == '__main__':
    unittest.main()

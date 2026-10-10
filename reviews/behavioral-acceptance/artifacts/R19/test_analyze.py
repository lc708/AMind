"""Fixed local tests; passing mocks do not establish real model behavior."""
import copy
import json
import math
import unittest
from pathlib import Path
from analyze import analyze, adoption_gate, load_pricer, normalize

ROOT = Path(__file__).parent
TASK = json.loads((ROOT / 'task.json').read_text())
FIXTURE = TASK['fixture']


class AccountingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pricer = load_pricer()

    def setUp(self):
        self.card, self.events = normalize(FIXTURE)

    def test_original_input_unchanged(self):
        before = copy.deepcopy(FIXTURE)
        normalize(FIXTURE)
        self.assertEqual(FIXTURE, before)

    def test_cached_and_reasoning_tokens_are_subsets(self):
        r = self.pricer.price(self.events[1], self.card)
        self.assertAlmostEqual(r['components']['uncached_input'], .001)
        self.assertAlmostEqual(r['components']['cached_input'], .0009)
        self.assertAlmostEqual(r['components']['output_including_reasoning'], .002)
        self.assertAlmostEqual(r['cost_usd'], .0039)
        self.assertEqual(r['status'], 'estimated_partial')

    def test_failed_spend_and_unknown_timeout_preserved(self):
        r = self.pricer.profile(self.events, self.card)
        self.assertAlmostEqual(r['known_or_estimated_subtotal_usd'], .0069)
        self.assertEqual(r['rows'][0]['status'], 'reported')
        self.assertEqual(r['rows'][0]['cost_usd'], .001)
        self.assertEqual(r['rows'][2]['cost_usd'], .002)
        self.assertEqual(r['unknown_events'], 1)
        self.assertEqual(r['partial_events'], 1)
        self.assertIsNone(r['total_cost_usd'])
        self.assertIsNone(r['rows'][3]['cost_usd'])

    def test_explicit_zero_differs_from_missing(self):
        event = copy.deepcopy(self.events[3])
        event['cost_usd'] = 0
        self.assertEqual(self.pricer.price(event, self.card)['status'], 'reported')
        event['cost_usd'] = None
        self.assertEqual(self.pricer.price(event, self.card)['status'], 'unknown')

    def test_missing_cache_counter_is_unknown(self):
        del self.events[1]['usage']['cached_input_tokens']
        self.assertEqual(self.pricer.price(self.events[1], self.card)['status'], 'unknown')

    def test_subset_violations_rejected(self):
        for field, value in [('cached_input_tokens', 1001), ('reasoning_tokens', 101)]:
            with self.subTest(field=field):
                event = copy.deepcopy(self.events[1])
                event['usage'][field] = value
                with self.assertRaises(ValueError):
                    self.pricer.price(event, self.card)

    def test_invalid_token_counts_rejected(self):
        for value in [-1, True, 1.5, float('nan'), float('inf')]:
            with self.subTest(value=value):
                event = copy.deepcopy(self.events[1])
                event['usage']['input_tokens'] = value
                with self.assertRaises(ValueError):
                    self.pricer.price(event, self.card)

    def test_invalid_reported_cost_rejected(self):
        for value in [-1, True, float('nan'), float('inf')]:
            event = copy.deepcopy(self.events[0])
            event['cost_usd'] = value
            with self.assertRaises(ValueError):
                self.pricer.price(event, self.card)

    def test_all_known_and_complete_control(self):
        # Synthetic counterexample, not a replacement of task.json evidence.
        self.events[1]['all_billable_usage_included'] = True
        self.events[3]['cost_usd'] = 0
        r = self.pricer.profile(self.events, self.card)
        self.assertAlmostEqual(r['total_cost_usd'], .0069)

    def test_external_charges_included(self):
        self.events[1]['external_charges_usd'] = [.003]
        self.assertAlmostEqual(self.pricer.price(self.events[1], self.card)['cost_usd'], .0069)

    def test_analysis_no_savings_claim(self):
        _, _, r = analyze(TASK)
        self.assertEqual(r['quality']['candidate_minus_baseline'], -.01)
        self.assertTrue(r['quality']['point_estimate_within_margin'])
        self.assertFalse(r['quality']['noninferiority_demonstrated'])
        self.assertIsNone(r['candidate_total_cost_usd'])
        self.assertIsNone(r['measured_relative_saving'])
        self.assertIsNone(r['cost_per_completed_useful_task_usd'])
        self.assertFalse(r['adoption']['adopt'])
        self.assertAlmostEqual(r['stage_subtotals']['application']['known_or_estimated_subtotal_usd'], .0049)
        self.assertAlmostEqual(r['cache_only_sensitivity']['maximum_relative_saving_over_known_subtotal'], .13043478260869565)
        self.assertFalse(r['cache_only_sensitivity']['passes_15_percent_even_under_these_assumptions'])


class DecisionTests(unittest.TestCase):
    def complete_mock(self):
        return dict.fromkeys(['paired_identity_verified', 'coverage_complete', 'cost_accounting_complete',
                              'mechanism_confirmed', 'hard_invariants_passed', 'slice_gates_passed',
                              'operations_passed', 'final_selection_frozen', 'independent_final_test_complete',
                              'simultaneous_intervals_verified'], True) | {
                                  'quality_difference_lower_bound': -.02, 'relative_saving_lower_bound': .15}

    def test_exact_registered_boundaries_pass_complete_mock(self):
        self.assertTrue(adoption_gate(self.complete_mock(), FIXTURE)['adopt'])

    def test_each_missing_or_failed_gate_blocks(self):
        for field in self.complete_mock():
            with self.subTest(field=field):
                e = self.complete_mock()
                del e[field]
                self.assertFalse(adoption_gate(e, FIXTURE)['adopt'])
                if isinstance(self.complete_mock()[field], bool):
                    e[field] = False
                    self.assertFalse(adoption_gate(e, FIXTURE)['adopt'])

    def test_unacceptable_loss_and_saving_block(self):
        for field, value in [('quality_difference_lower_bound', -.02001), ('relative_saving_lower_bound', .14999)]:
            e = self.complete_mock()
            e[field] = value
            self.assertFalse(adoption_gate(e, FIXTURE)['adopt'])

    def test_nonfinite_bool_and_missing_bounds_block(self):
        for field in ['quality_difference_lower_bound', 'relative_saving_lower_bound']:
            for value in [None, True, math.inf, math.nan]:
                e = self.complete_mock()
                e[field] = value
                self.assertFalse(adoption_gate(e, FIXTURE)['adopt'])

    def test_point_means_alone_never_pass(self):
        self.assertFalse(adoption_gate({'quality_difference_lower_bound': -.01}, FIXTURE)['adopt'])


if __name__ == '__main__':
    unittest.main()

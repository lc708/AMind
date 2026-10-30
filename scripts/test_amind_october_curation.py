#!/usr/bin/env python3
"""Meaningful date, provenance and history regressions for the October refresh."""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import curate_amind_october_30 as curate

spec = importlib.util.spec_from_file_location('october_lifecycle', ROOT / 'skills/amind/scripts/lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


def unit(identity, canonical, body, publication='2026-10-19', month=''):
    return {
        'analysis_unit_id': identity, 'canonical': canonical,
        'published_at': publication, 'observed_at': '2026-10-29T18:30:00+00:00',
        'raw_sha256': 'a' * 64, 'source_seed_record_ids': ['record-' + identity],
        'extraction': {'date_evidence': ([{'kind': 'visible_month_only; exact day unavailable', 'value': month}]
                                       if month else [])},
    }


def passage(identity, body):
    return {'passage_id': 'p-' + identity, 'analysis_unit_id': identity, 'passage_sequence': 1,
            'source_char_start': 0, 'source_char_end': len(body), 'text': body, 'section_path': []}


def claim(identity, source, body, quote):
    start = body.index(quote)
    return {'claim_id': identity, 'conditions': [], 'epistemic_force': 'asserted',
            'voice': {'organization': 'Anthropic', 'attribution_basis': 'Native byline.'},
            'provenance': {'review_state': 'machine_checked'},
            'evidence': [{'analysis_unit_id': source, 'passage_id': 'p-' + source,
                          'exact_quote': quote, 'exact_quote_sha256': curate.digest(quote.encode()),
                          'source_char_start': start, 'source_char_end': start + len(quote)}]}


def fixture():
    old_quotes = [
        'We will keep our public Constitution up to date and run a systematic oversight process over our training data.',
        'We believe we can develop a method for red-teaming our systems.',
        'We expect to publish a new goal in the coming weeks.',
        'We maintain strong safeguards.',
    ]
    old_body = '\n\n'.join(old_quotes)
    old_unit = unit('old-roadmap', curate.ROADMAP, old_body, '2026-07-10')
    old_claims = [claim('old-' + str(i), 'old-roadmap', old_body, quote) for i, quote in enumerate(old_quotes)]
    new_quotes = [
        'We no longer run it routinely.',
        'It matched or beat the best human submission in all 24 question-classifier pairs.',
        'We added two new policy goals due December 15 and due January 15.',
        'We now use the term inference verification.',
        'We maintain strong safeguards.',
    ]
    new_body = '# Roadmap\n\nOctober 19, 2026\n\n' + '\n\n'.join(new_quotes)
    new_unit = unit('new-roadmap', curate.ROADMAP, new_body)
    new_claims = [claim('new-' + str(i), 'new-roadmap', new_body, quote) for i, quote in enumerate(new_quotes)]
    required = [{'claim_id': old_claims[i]['claim_id'],
                 'quote_sha256': old_claims[i]['evidence'][0]['exact_quote_sha256'], 'key': key}
                for i, key in enumerate(('constitution', 'redteam', 'policy'))]
    previous = [curate.make_status('historical_only', ['old-unchanged-registry-row'],
                                  'https://example.com/old', 'Frozen old decision.',
                                  '2026-10-18T00:00:00+00:00', valid_until='2026-09-01')]
    values = {'units': [new_unit], 'passages': [passage('new-roadmap', new_body)], 'claims': new_claims,
              'old_units': [old_unit], 'old_passages': [passage('old-roadmap', old_body)],
              'old_claims': old_claims, 'previous_status': previous, 'required_targets': required}
    return values


class CurationTests(unittest.TestCase):
    def test_old_registry_and_unchanged_propositions_survive(self):
        values = fixture(); frozen = copy.deepcopy(values)
        result = curate.curate_rows(**values)
        self.assertEqual(result['current-status'][0], values['previous_status'][0])
        self.assertEqual(values, frozen)
        targets = {cid for row in result['current-status-additions'] for cid in row['target_claim_ids']}
        self.assertTrue({'old-0', 'old-1', 'old-2'} <= targets)
        self.assertNotIn('old-3', targets)
        self.assertFalse(any('old-roadmap' in row['target_analysis_unit_ids']
                             for row in result['current-status-additions']))

    def test_retirement_begins_on_public_date(self):
        values = fixture(); result = curate.curate_rows(**values)
        query = {'claim_id': 'old-1', 'analysis_unit_id': 'old-roadmap', 'source_published_at': '2026-07-10'}
        before = lifecycle.assess(query, result['current-status'], '2026-10-18', '2026-10-30')
        after = lifecycle.assess(query, result['current-status'], '2026-10-19', '2026-10-30')
        self.assertTrue(before['eligible'])
        self.assertFalse(after['eligible'])
        self.assertIn('superseded', after['reasons'])

    def test_dated_revision_is_not_hidden_until_its_later_capture(self):
        values = fixture(); values['units'][0]['published_at'] = ''
        result = curate.curate_rows(**values)
        query = {'claim_id': 'new-0', 'analysis_unit_id': 'new-roadmap', 'source_published_at': ''}
        self.assertFalse(lifecycle.assess(query, result['current-status'], '2026-10-18', '2026-10-30')['eligible'])
        self.assertTrue(lifecycle.assess(query, result['current-status'], '2026-10-19', '2026-10-30')['eligible'])

    def test_real_legal_center_header_keeps_the_future_effective_date(self):
        for path, title in [('/legal/aup', 'Usage Policy'),
                            ('/legal/supported-regions', 'Supported Regions Policy')]:
            with self.subTest(path=path):
                values = fixture()
                # Exact new template observed in both captured policy bodies.
                body = ('# Legal center\n\n# ' + title + '\n\nDownload PDF\n\n'
                        '- Effective\n\nNov 12, 2026\n\n- Type\n\nPolicy\n\n'
                        'This policy sets the terms for supported use.')
                values['units'].append(unit('legal', 'https://anthropic.com' + path, body, ''))
                values['passages'].append(passage('legal', body))
                result = curate.curate_rows(**values)
                lifecycle.validate_records(result['current-status'])
                query = {'claim_id': 'legal-rule', 'analysis_unit_id': 'legal', 'source_published_at': ''}
                captured = lifecycle.assess(query, result['current-status'], '2026-10-30', '2026-10-30')
                self.assertFalse(captured['eligible'])
                self.assertIn('not_yet_effective', captured['reasons'])
                self.assertFalse(lifecycle.assess(query, result['current-status'], '2026-11-11', '2026-10-30')['eligible'])
                self.assertTrue(lifecycle.assess(query, result['current-status'], '2026-11-12', '2026-10-30')['eligible'])
                self.assertEqual(values['units'][-1]['published_at'], '')

    def test_older_full_month_legal_header_has_the_same_boundary(self):
        values = fixture()
        body = '# Usage Policy\n\nEffective November 12, 2026Previous Version\n\nPolicy rules.'
        values['units'].append(unit('legal', 'https://anthropic.com/legal/aup', body, ''))
        values['passages'].append(passage('legal', body))
        result = curate.curate_rows(**values)
        rules = [row for row in result['current-status']
                 if row['kind'] == 'effective_window' and row['target_analysis_unit_ids'] == ['legal']]
        self.assertEqual([row['valid_from'] for row in rules], ['2026-11-12'])

    def test_deprecation_manual_switches_on_capture_not_model_retirement(self):
        values = fixture()
        url = 'https://platform.claude.com/docs/en/about-claude/model-deprecations'
        old_body = ('# Model deprecations\n\nPartner-operated platforms (Amazon Bedrock and Google Cloud) '
                    'set their own retirement schedules.\n\nThis model was retired April 20, 2026.')
        new_body = ('# Model deprecations\n\nClaude Models on Google Cloud (Anthropic managed) follows '
                    'Anthropic-operated schedules. Claude Models on Google Cloud (Google managed) sets '
                    'its own schedule.\n\nThis model was retired April 20, 2026.')
        values['old_units'].append(unit('old-manual', url, old_body, '2026-04-20'))
        values['old_passages'].append(passage('old-manual', old_body))
        values['units'].append(unit('new-manual', url, new_body, ''))
        values['passages'].append(passage('new-manual', new_body))
        result = curate.curate_rows(**values)
        lifecycle.validate_records(result['current-status'])
        for as_of, old_eligible, new_eligible in [('2026-10-29', True, False), ('2026-10-30', False, True)]:
            with self.subTest(as_of=as_of):
                old_query = {'claim_id': 'old-rule', 'analysis_unit_id': 'old-manual', 'source_published_at': '2026-04-20'}
                new_query = {'claim_id': 'new-rule', 'analysis_unit_id': 'new-manual', 'source_published_at': ''}
                self.assertEqual(lifecycle.assess(old_query, result['current-status'], as_of, '2026-10-30')['eligible'], old_eligible)
                self.assertEqual(lifecycle.assess(new_query, result['current-status'], as_of, '2026-10-30')['eligible'], new_eligible)
        transition = next(row for row in result['current-status-additions']
                          if row['kind'] == 'superseded' and row['target_analysis_unit_ids'] == ['old-manual'])
        self.assertEqual(transition['valid_until'], '2026-10-30')
        self.assertEqual(transition['replacement_analysis_unit_ids'], ['new-manual'])
        self.assertEqual(values['units'][-1]['published_at'], '')

    def test_full_goal_review_retires_pending_wording_but_keeps_continuing_mechanisms(self):
        values = fixture()
        pending = [
            'We will establish an internal jailbreak-finding method for classifier guards.',
            'We will assess this via a report that compares the findings.',
            'This could put us in position to continue leveling up over time.',
            'We already have safeguards, but aim to make these measures more complete and systematic.',
            'We will run an oversight process over a representative sample of our production-relevant post-training data.',
            'We will complete Phase 1 by May 15, 2026.',
            'We will develop a prototype by September 30, 2026 of provable inference.',
            'The Phase 1 deadline is September 30, 2026.',
        ]
        continuing = [
            'We will perform systematic alignment assessments.',
            'We will update the public Constitution within 90 days of relevant internal or external deployments.',
            'Security is fundamentally about the strength of the weakest link.',
        ]
        body = values['old_passages'][0]['text'] + '\n\n' + '\n\n'.join(pending + continuing)
        values['old_passages'][0] = passage('old-roadmap', body)
        for index, quote in enumerate(pending + continuing):
            values['old_claims'].append(claim('goal-' + str(index), 'old-roadmap', body, quote))
        result = curate.curate_rows(**values)
        for index in range(len(pending) + len(continuing)):
            query = {'claim_id': 'goal-' + str(index), 'analysis_unit_id': 'old-roadmap', 'source_published_at': '2026-07-10'}
            self.assertTrue(lifecycle.assess(query, result['current-status'], '2026-10-18', '2026-10-30')['eligible'])
            self.assertEqual(lifecycle.assess(query, result['current-status'], '2026-10-19', '2026-10-30')['eligible'], index >= len(pending))

    def test_missing_replacement_is_not_silently_accepted(self):
        values = fixture(); values['claims'] = [row for row in values['claims'] if row['claim_id'] != 'new-1']
        with self.assertRaisesRegex(curate.CurationError, 'replacement evidence absent'):
            curate.curate_rows(**values)

    def test_changed_old_quote_is_not_a_valid_target(self):
        values = fixture(); values['required_targets'][0]['quote_sha256'] = 'b' * 64
        with self.assertRaisesRegex(curate.CurationError, 'old claim quote changed'):
            curate.curate_rows(**values)

    def test_context_review_checks_source_offsets(self):
        values = fixture(); values['claims'][0]['evidence'][0]['source_char_start'] += 1
        with self.assertRaisesRegex(curate.CurationError, 'offset drift'):
            curate.curate_rows(**values)

    def test_reviews_preserve_quotes_ids_and_input_objects(self):
        values = fixture(); result = curate.curate_rows(**values)
        frozen = copy.deepcopy(values['claims'])
        applied = curate.apply_claim_reviews(values['claims'], result['claim-reviews'], result['source-scope-notes'])
        self.assertEqual(values['claims'], frozen)
        self.assertEqual([row['claim_id'] for row in applied], [row['claim_id'] for row in frozen])
        self.assertEqual([row['evidence'] for row in applied], [row['evidence'] for row in frozen])
        self.assertEqual(applied, curate.apply_claim_reviews(applied, result['claim-reviews'], result['source-scope-notes']))

    def test_review_binding_drift_is_rejected(self):
        values = fixture(); result = curate.curate_rows(**values)
        result['claim-reviews'][0]['exact_quote_sha256'] = 'c' * 64
        with self.assertRaisesRegex(curate.CurationError, 'binding drift'):
            curate.apply_claim_reviews(values['claims'], result['claim-reviews'])

    def test_ai_review_cannot_promote_human_gold(self):
        values = fixture(); result = curate.curate_rows(**values)
        result['claim-reviews'][0]['human_gold_promotion'] = True
        with self.assertRaisesRegex(curate.CurationError, 'cannot promote human Gold'):
            curate.apply_claim_reviews(values['claims'], result['claim-reviews'])

    def test_archival_promise_does_not_hide_following_update_paragraphs(self):
        values = fixture()
        body = ('# Previous goals\n\n## World-class internal red-teaming\n\n'
                '#### Version of this goal as set on: February 19, 2026\n\n'
                'We will establish a method.\n\nUpdate\n\n'
                'October 19, 2026: We completed this goal.\n\n'
                'It matched or beat the best human submission.\n')
        values['units'].append(unit('archive', curate.UPDATES, body))
        values['passages'].append(passage('archive', body))
        values['claims'] += [claim('archive-promise', 'archive', body, 'We will establish a method.'),
                             claim('archive-result', 'archive', body, 'It matched or beat the best human submission.')]
        result = curate.curate_rows(**values)
        historic = {cid for row in result['current-status-additions'] if row['kind'] == 'historical_only'
                    for cid in row['target_claim_ids']}
        self.assertIn('archive-promise', historic)
        self.assertNotIn('archive-result', historic)

    def test_curation_is_deterministic(self):
        values = fixture()
        self.assertEqual(curate.curate_rows(**values), curate.curate_rows(**copy.deepcopy(values)))

    def test_collaborative_source_host_does_not_create_institutional_attribution(self):
        body = 'We propose GRAFT as a scoped experiment.'
        candidate = claim('graft-claim', 'graft', body, body)
        notes = [{'analysis_unit_id': 'graft', 'scope_notes': ['Scoped collaboration.'],
                  'clear_institutional_organization': True}]
        applied = curate.apply_claim_reviews([candidate], [], notes)
        self.assertEqual(applied[0]['voice']['organization'], '')
        self.assertEqual(candidate['voice']['organization'], 'Anthropic')

    def test_charter_end_state_is_not_an_achieved_fact(self):
        body = ('# Public Benefit Report\n\n## Charter pillars\n\n'
                'The technical problems of AI safety are solved.\n\n## Explore the work\n')
        source = unit('benefit', 'https://anthropic.com/public-benefit-report', body, '')
        scope = curate.public_benefit_scope(source, body)
        candidate = claim('benefit-goal', 'benefit', body, 'The technical problems of AI safety are solved.')
        applied = curate.apply_claim_reviews([candidate], [], [scope])[0]
        self.assertEqual(applied['claim_type'], 'normative')
        self.assertEqual(applied['epistemic_force'], 'qualified')
        self.assertTrue(any('not a claim' in text for text in applied['conditions']))

    def test_trust_commentary_keeps_its_own_voice(self):
        body = ('## Page 1\n\nContents\n\n## Page 2\n\nForeword.\n\n## Page 4\n\n'
                '1. The technical problems are solved.\n\nThis report takes stock.\n\n'
                '## Page 17\n\nRight now, it largely describes inputs.\n\n'
                '## Page 19\n\nBoard adoption.\n\nPillar 1\n\nSafety is solved.\n\n## Page 20\n\nPillar 5.\n')
        source = unit('benefit-pdf', 'https://www-cdn.anthropic.com/' + curate.PUBLIC_BENEFIT_PDF, body, '')
        scope = curate.public_benefit_scope(source, body)
        candidate = claim('trust-inputs', 'benefit-pdf', body, 'Right now, it largely describes inputs.')
        candidate['epistemic_force'] = 'quoted_position'
        applied = curate.apply_claim_reviews([candidate], [], [scope])[0]
        self.assertEqual(applied['voice']['name'], 'Buddy Shah on behalf of the Long-Term Benefit Trust')
        self.assertEqual(applied['epistemic_force'], 'quoted_position')
        self.assertTrue(any('not an external independent' in note for note in applied['conditions']))

    def test_scope_review_does_not_turn_forecasts_into_observed_results(self):
        values = fixture()
        body = 'We hope localizing learning updates will help in future experiments.'
        values['units'].append(unit('graft', 'https://alignment.anthropic.com/2026/graft', body))
        values['passages'].append(passage('graft', body))
        candidate = claim('graft-forecast', 'graft', body, body)
        candidate['epistemic_force'] = 'forecast'; values['claims'].append(candidate)
        result = curate.curate_rows(**values)
        applied = curate.apply_claim_reviews(values['claims'], result['claim-reviews'], result['source-scope-notes'])
        self.assertEqual(next(row for row in applied if row['claim_id'] == 'graft-forecast')['epistemic_force'], 'forecast')

    def test_newly_indexed_plan_can_already_be_fulfilled(self):
        values = fixture()
        plan = 'We will publish an upcoming public benefit report.'
        witness = 'This week we published our first Public Benefit Report.'
        for identity, url, body, published in [
            ('fund', 'https://anthropic.com/news/public-benefit-fund', plan, '2026-10-18'),
            ('stubbs', 'https://anthropic.com/news/christopher-stubbs-joins-long-term-benefit-trust', witness, '2026-10-21'),
        ]:
            values['units'].append(unit(identity, url, body, published))
            values['passages'].append(passage(identity, body))
            values['claims'].append(claim(identity + '-claim', identity, body, body))
        result = curate.curate_rows(**values)
        transition = next(row for row in result['current-status-additions'] if 'fund-claim' in row['target_claim_ids'])
        self.assertEqual(transition['valid_until'], '2026-10-21')
        self.assertEqual(transition['replacement_claim_ids'], ['stubbs-claim'])
        self.assertEqual(values['units'][-1]['published_at'], '2026-10-21')


class AvailabilityTests(unittest.TestCase):
    def status(self, month='October 2026'):
        values = fixture()
        body = '# Undated source\n\nThis source has been captured.'
        values['units'].append(unit('undated', 'https://example.com/undated', body, '', month))
        values['passages'].append(passage('undated', body))
        result = curate.curate_rows(**values)
        return next(row for row in result['current-status-additions']
                    if row['kind'] == 'publication_window' and row['target_analysis_unit_ids'] == ['undated'])

    def test_month_precision_remains_unknown_day_after_observation(self):
        status = self.status(); lifecycle.validate_records([status])
        query = {'claim_id': 'x', 'analysis_unit_id': 'undated', 'source_published_at': ''}
        before = lifecycle.assess(query, [status], '2026-10-29', '2026-10-30')
        after = lifecycle.assess(query, [status], '2026-10-30', '2026-10-30')
        self.assertFalse(before['eligible'])
        self.assertTrue(after['eligible'])
        self.assertEqual(after['publication_date_precision'], 'month')
        self.assertFalse(after['publication_day_known'])
        self.assertEqual(after['publication_available_by'], '2026-10-30')
        self.assertEqual(after['publication_availability'], 'available')

    def test_wholly_unknown_date_has_conservative_history(self):
        status = self.status(''); lifecycle.validate_records([status])
        query = {'claim_id': 'x', 'analysis_unit_id': 'undated', 'source_published_at': ''}
        before = lifecycle.assess(query, [status], '2026-10-18', '2026-10-30')
        after = lifecycle.assess(query, [status], '2026-10-30', '2026-10-30')
        self.assertEqual(before['publication_availability'], 'uncertain')
        self.assertIn('publication_availability_unconfirmed', before['reasons'])
        self.assertTrue(after['eligible'])
        self.assertEqual(after['publication_date_precision'], 'unknown')
        self.assertIsNone(after['publication_earliest_possible'])

    def test_capture_cannot_assert_an_earlier_available_date(self):
        status = self.status(); status['available_by'] = '2026-10-29'
        with self.assertRaisesRegex(ValueError, 'unsupported publication availability'):
            lifecycle.validate_records([status])

    def test_capture_proof_cannot_be_omitted(self):
        status = self.status(); del status['availability_evidence']
        with self.assertRaisesRegex(ValueError, 'unbound publication availability'):
            lifecycle.validate_records([status])

    def test_proof_must_bind_the_target_and_source(self):
        status = self.status(); status['availability_evidence']['analysis_unit_id'] = 'other'
        with self.assertRaisesRegex(ValueError, 'unbound publication availability'):
            lifecycle.validate_records([status])
        status = self.status(); status['availability_evidence']['source_canonical'] = 'https://example.com/other'
        with self.assertRaisesRegex(ValueError, 'unbound publication availability'):
            lifecycle.validate_records([status])

    def test_capture_timestamp_requires_a_timezone(self):
        status = self.status(); status['availability_evidence']['observed_at'] = '2026-10-30T02:00:00'
        with self.assertRaisesRegex(ValueError, 'invalid publication observation'):
            lifecycle.validate_records([status])

    def test_invalid_month_is_not_hidden_by_valid_capture(self):
        status = self.status(''); status['publication_month'] = '2026-99'
        with self.assertRaisesRegex(ValueError, 'invalid publication month'):
            lifecycle.validate_records([status])

    def test_legacy_month_window_keeps_existing_behavior(self):
        status = {'status_id': 'old-month', 'kind': 'publication_window',
                  'target_analysis_unit_ids': ['undated'], 'valid_from': '2026-10-01',
                  'publication_month': '2026-10', 'source_canonical': 'https://example.com/undated',
                  'reason': 'Native month only.'}
        lifecycle.validate_records([status])
        query = {'claim_id': 'x', 'analysis_unit_id': 'undated', 'source_published_at': ''}
        self.assertFalse(lifecycle.assess(query, [status], '2026-10-30', '2026-10-30')['eligible'])
        self.assertTrue(lifecycle.assess(query, [status], '2026-10-31', '2026-10-30')['eligible'])


if __name__ == '__main__':
    unittest.main()

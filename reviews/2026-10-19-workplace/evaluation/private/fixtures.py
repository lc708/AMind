"""Private synthetic incident fixtures. Never copy into a target repository."""
import copy

IDENTITY = {'provider': 'fixture', 'interface': 'responses', 'model': 'support-model', 'service_tier': 'standard', 'region': 'global'}
RATE_CARD = {'version': 'incident-2026-09-30', 'effective_date': '2026-09-30', 'source': 'Synthetic audited exercise rates; not provider prices',
             'rates': [{'identity': IDENTITY, 'mode': 'text', 'input_per_million': 10, 'cached_per_million': 1, 'output_per_million': 20},
                       {'identity': {**IDENTITY, 'interface': 'decisions'}, 'mode': 'input_only', 'input_per_million': 2}]}
COVERAGE = {'stages': [{'id': 'workers', 'total': 3, 'coverage': 1, 'counts': {'succeeded': 3}, 'uncovered': []},
                       {'id': 'aggregate', 'total': 1, 'coverage': 1, 'counts': {'succeeded': 1}, 'uncovered': []}]}


def release():
    manifest = {'release_id': 'support-autoreply-47', 'variant': 'candidate', 'split': 'validation', 'case_ids': ['refund', 'account-lock'],
                'repetitions': 1, 'comparison_hash': 'measurement-2026-09-30', 'treatment_hash': 'prompt-v47',
                'expected_billing_identity': IDENTITY, 'required_stages': {'workers': 3, 'aggregate': 1},
                'metrics': [{'id': 'quality', 'min': 0, 'max': 1, 'min_mean': .75}]}
    results, events = [], []
    for n, case in enumerate(manifest['case_ids']):
        results.append({'case_id': case, 'rep': 0, 'status': 'ok', 'grade': {'quality': [.8, 1][n]},
                        'result_identity': {'comparison_hash': manifest['comparison_hash'], 'treatment_hash': manifest['treatment_hash'], 'case_id': case, 'rep': 0},
                        'billing_identity': IDENTITY, 'coverage': copy.deepcopy(COVERAGE)})
        events.extend([{'event': 'started', 'attempt_id': 'call-' + case, 'case_id': case, 'rep': 0},
                       {'event': 'finished', 'attempt_id': 'call-' + case, 'case_id': case, 'rep': 0, 'status': 'ok', 'cost_usd': .2}])
    return copy.deepcopy((manifest, results, events, RATE_CARD))


def cohort(conf=None, dataset='support-holdout-9', judge='judge-current'):
    conf = conf or {'tp': 2, 'tn': 2, 'fp': 1, 'fn': 1}
    rows = []
    for kind, count in conf.items():
        for i in range(count):
            rows.append({'id': kind + '-' + str(i), 'family': 'family-' + str(len(rows) % 20), 'split': 'holdout',
                         'human': int(kind in ('tp', 'fn')), 'decision': int(kind in ('tp', 'fp'))})
    return {'identity': {'dataset_version': dataset, 'judge': judge, 'grader_version': judge, 'rubric': 'issue-detection-7'}, 'records': rows}


def calibration():
    return {'incident_id': 'judge-rollout-47', 'positive_event': 'genuine_support_policy_issue', 'current': cohort(),
            'deployment_prevalence': .001, 'required_workers': ['billing', 'support', 'security'],
            'worker_reports': [{'id': key, 'status': 'succeeded'} for key in ('billing', 'support', 'security')],
            'limits': {'max_fpr_increase': .03, 'min_labeled_families': 2}}

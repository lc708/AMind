#!/usr/bin/env python3
import copy
import json
from fixtures import calibration, cohort
from grader_common import evaluate


def probes():
    rows = []
    def add(key, domain, job, expected): rows.append((key, domain, job, expected))
    j = calibration()
    add('clean-reviewed', 'class_rates', j, {'calibration.confusion': {'tp': 2, 'tn': 2, 'fp': 1, 'fn': 1}, 'calibration.fpr': 1/3, 'calibration.fnr': 1/3, 'status': 'ready_for_review'})
    j = calibration(); j['current'] = cohort({'tp': 90, 'fn': 10, 'fp': 18, 'tn': 882})
    add('deployment-base-rate', 'class_rates', j, {'calibration.fpr': .02, 'calibration.fnr': .1, 'calibration.precision': 90/108, 'deployment_precision.status': 'scenario', 'deployment_precision.value': .04310344827586207})
    j = calibration(); j['current'] = cohort({'tp': 3})
    add('absent-negative-control', 'class_rates', j, {'calibration.fpr': None, 'calibration.unmeasured': ['false_positive_rate'], 'status': 'hold'})
    j = calibration(); j['current']['records'][2]['decision'] = None
    add('abstention-visible', 'missingness', j, {'calibration.denominators.abstained': 1, 'calibration.denominators.evaluated': 5, 'calibration.denominators.evaluated_negative': 2, 'calibration.judgment_coverage': 5/6, 'status': 'hold'})
    j = calibration(); j['current']['records'][4]['human'] = None
    add('unknown-adjudication', 'missingness', j, {'calibration.denominators.unknown_human': 1, 'calibration.denominators.evaluated': 5, 'calibration.confusion.fp': 0, 'status': 'hold'})
    j = calibration()
    for r in j['current']['records']: r['family'] = 'same-incident-family'
    add('family-denominator', 'family_holdout', j, {'family_count': 1, 'status': 'hold'})
    j = calibration(); j['current']['records'][0].update(family='customer-incident', split='train'); j['current']['records'][1].update(family='customer-incident')
    add('cross-split-family', 'family_holdout', j, {'integrity.status': 'invalid', 'status': 'hold'})
    j = calibration(); j['current']['records'].append(copy.deepcopy(j['current']['records'][0]))
    add('duplicate-calibration-row', 'family_holdout', j, {'integrity.status': 'invalid', 'calibration.denominators.evaluated': 6, 'status': 'hold'})
    j = calibration(); j['baseline'] = copy.deepcopy(j['current']); j['baseline']['identity'].update(judge='previous-judge', grader_version='previous-grader'); j['baseline']['records'][0]['decision'] = 0; j['current']['records'][2]['decision'] = 1
    add('paired-change', 'paired_judges', j, {'paired.status': 'complete', 'paired.pairs': 6, 'paired.evaluated_pairs': 6, 'paired.improved': 1, 'paired.regressed': 1, 'paired.agreement_delta': 0.0})
    j = calibration(); j['baseline'] = copy.deepcopy(j['current']); j['baseline']['records'].pop()
    add('paired-missing-case', 'paired_judges', j, {'paired.status': 'invalid', 'integrity.status': 'invalid', 'status': 'hold'})
    j = calibration(); j['baseline'] = copy.deepcopy(j['current']); j['baseline']['records'][0]['decision'] = None
    add('paired-abstention', 'paired_judges', j, {'paired.status': 'partial', 'paired.pairs': 6, 'paired.evaluated_pairs': 5, 'status': 'hold'})
    j = calibration(); j['current'] = cohort({'tp': 10, 'fp': 8, 'tn': 92}, 'current-cohort'); j['drift_reference'] = cohort({'tp': 10, 'fp': 2, 'tn': 98}, 'prior-cohort')
    add('fixed-judge-drift', 'drift_workers', j, {'drift.status': 'alert', 'drift.fpr_delta': .06, 'status': 'hold'})
    j = calibration(); j['drift_reference'] = copy.deepcopy(j['current']); j['drift_reference']['identity']['judge'] = 'another-judge'
    add('changed-judge-not-drift', 'drift_workers', j, {'drift.status': 'invalid', 'drift.fpr_delta': None, 'integrity.status': 'invalid', 'status': 'hold'})
    j = calibration(); j['worker_reports'] = [{'id': 'billing', 'status': 'succeeded'}, {'id': 'support', 'status': 'succeeded'}, {'id': 'security', 'status': 'unknown'}]
    add('unknown-worker', 'drift_workers', j, {'workers.expected': 3, 'workers.completed': 2, 'workers.uncovered': ['security'], 'workers.status': 'incomplete', 'status': 'hold'})
    return rows


if __name__ == '__main__':
    print(json.dumps(evaluate('V-CALIBRATE', 'judgecheck', probes(), ['class_rates', 'missingness', 'family_holdout', 'paired_judges', 'drift_workers'],
                              {'no_clean_control_false_pass': ['absent-negative-control'], 'holdout_family_integrity': ['cross-split-family'], 'no_pair_dropping': ['paired-missing-case'], 'unknown_worker_not_success': ['unknown-worker']}), allow_nan=False))

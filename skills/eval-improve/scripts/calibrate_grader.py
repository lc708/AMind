#!/usr/bin/env python3
"""Audit judge error rates, base rates, identity, paired changes and drift offline."""
import argparse
import json
import statistics
import sys
from pathlib import Path
from kernel_common import finite, read_jsonl, sha

IDENTITY_FIELDS = ('dataset_version', 'grader_version', 'rubric_sha256', 'judge_model')


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def identity_of(rows):
    identities = [row.get('evaluation_identity') for row in rows]
    if all(value is None for value in identities): return None
    for value in identities:
        if not isinstance(value, dict) or any(not isinstance(value.get(k), str) or not value[k] for k in IDENTITY_FIELDS):
            raise ValueError('every identified row needs dataset_version/grader_version/rubric_sha256/judge_model')
    if any(value != identities[0] for value in identities):
        raise ValueError('mixed evaluation identities; recalibrate each fixed judge/rubric/dataset separately')
    return identities[0]


def calibrate(rows, population_prevalence=None):
    if not rows: raise ValueError('calibration requires adjudicated examples')
    identity = identity_of(rows)
    if population_prevalence is not None and (not finite(population_prevalence) or not 0 <= population_prevalence <= 1):
        raise ValueError('population prevalence must be between zero and one')
    counts = {'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0}; disagreements = []; grouped = {}; swaps = []
    seen = set(); human_by_id = {}
    for row in rows:
        key = (row.get('id'), row.get('rep', 0))
        if not isinstance(key[0], str) or not key[0] or type(key[1]) is not int or key[1] < 0 or key in seen:
            raise ValueError('unique string id and nonnegative rep required')
        seen.add(key)
        human, grade = row.get('human'), row.get('grade')
        if type(human) not in (int, bool) or type(grade) not in (int, bool) or human not in (0, 1) or grade not in (0, 1):
            raise ValueError('human and grade must be adjudicated binary labels')
        if key[0] in human_by_id and human_by_id[key[0]] != human:
            raise ValueError('human adjudication changed across repetitions')
        human_by_id[key[0]] = human
        counts['tp' if grade and human else 'fp' if grade else 'fn' if human else 'tn'] += 1
        if human != grade: disagreements.append({'id': key[0], 'rep': key[1], 'human': human, 'grade': grade})
        grouped.setdefault(key[0], []).append(grade)
        if 'swapped_grade' in row:
            swapped = row['swapped_grade']
            if type(swapped) not in (int, bool) or swapped not in (0, 1): raise ValueError('swapped_grade must be binary')
            swaps.append(grade != 1 - swapped)
    positives = counts['tp'] + counts['fn']; negatives = counts['tn'] + counts['fp']
    tpr = ratio(counts['tp'], positives); fpr = ratio(counts['fp'], negatives)
    adjusted_precision = None
    if population_prevalence is not None and tpr is not None and fpr is not None:
        adjusted_precision = ratio(tpr * population_prevalence, tpr * population_prevalence + fpr * (1 - population_prevalence))
    status = {'positive_controls': 'measured' if positives else 'unmeasured',
              'negative_controls': 'measured' if negatives else 'unmeasured',
              'order_bias': 'measured' if swaps else 'unmeasured',
              'repeat_stability': 'measured' if any(len(v) > 1 for v in grouped.values()) else 'unmeasured',
              'population_precision': 'scenario_estimate' if adjusted_precision is not None else 'unmeasured',
              'identity': 'verified' if identity else 'legacy_unverified'}
    return {'examples': len(grouped), 'judgments': len(rows), 'confusion': counts,
            'evaluation_identity': identity, 'labels_sha256': sha(rows), 'measurement_status': status,
            'positive_judgments': positives, 'negative_judgments': negatives,
            'agreement': (counts['tp'] + counts['tn']) / len(rows),
            'precision': ratio(counts['tp'], counts['tp'] + counts['fp']), 'recall': tpr,
            'false_positive_rate': fpr, 'false_negative_rate': ratio(counts['fn'], positives),
            'specificity': ratio(counts['tn'], negatives),
            'sample_prevalence': positives / len(rows), 'population_prevalence': population_prevalence,
            'population_adjusted_precision': adjusted_precision,
            'disagreements': disagreements,
            'unstable_cases': [key for key, values in grouped.items() if len(set(values)) > 1],
            'order_inconsistency_rate': statistics.mean(swaps) if swaps else None,
            'ready_for_review': (identity is not None and all(status[k] == 'measured' for k in
                                 ('positive_controls', 'negative_controls', 'order_bias', 'repeat_stability'))
                                 and not disagreements and not any(swaps)
                                 and all(len(set(v)) == 1 for v in grouped.values())),
            'limits': 'Positive means the declared event, not automatically a safety violation. Curated/repeated samples are not independent population estimates. Base-rate precision is a scenario using supplied prevalence. Unmeasured checks do not pass. Human review must address auditor reward hacking, negative controls and rubric attacks.'}


def paired(baseline, candidate):
    left, right = calibrate(baseline), calibrate(candidate)
    if left['evaluation_identity'] is None or right['evaluation_identity'] is None:
        raise ValueError('paired judge comparison requires identified labels')
    for field in ('dataset_version', 'rubric_sha256'):
        if left['evaluation_identity'][field] != right['evaluation_identity'][field]:
            raise ValueError('paired judges require the same dataset and rubric')
    key = lambda row: (row['id'], row.get('rep', 0))
    a, b = {key(r): r for r in baseline}, {key(r): r for r in candidate}
    if set(a) != set(b) or any(a[k]['human'] != b[k]['human'] for k in a):
        raise ValueError('paired judges require identical case/repetition/adjudication sets')
    improved = sum(a[k]['grade'] != a[k]['human'] and b[k]['grade'] == b[k]['human'] for k in a)
    regressed = sum(a[k]['grade'] == a[k]['human'] and b[k]['grade'] != b[k]['human'] for k in a)
    return {'status': 'measured_descriptive', 'pairs': len(a), 'improved': improved, 'regressed': regressed,
            'agreement_delta': (improved - regressed) / len(a),
            'baseline_labels_sha256': left['labels_sha256'], 'candidate_labels_sha256': right['labels_sha256'],
            'limits': 'Paired descriptive counts; no population improvement or confidence claim. Average repetitions and resample independent groups for inferential comparisons.'}


def drift(reference, current, max_fpr_increase=0):
    if not finite(max_fpr_increase) or not 0 <= max_fpr_increase <= 1:
        raise ValueError('max FPR increase must be between zero and one')
    old, new = calibrate(reference), calibrate(current)
    a, b = old['evaluation_identity'], new['evaluation_identity']
    if a is None or b is None: raise ValueError('drift audit requires identified labels')
    for field in ('grader_version', 'rubric_sha256', 'judge_model'):
        if a[field] != b[field]: raise ValueError('drift audit requires the same judge and rubric; use paired for judge changes')
    delta = None if old['false_positive_rate'] is None or new['false_positive_rate'] is None else new['false_positive_rate'] - old['false_positive_rate']
    return {'status': 'unmeasured' if delta is None else 'alert' if delta > max_fpr_increase else 'within_registered_margin',
            'false_positive_rate_delta': delta, 'max_fpr_increase': max_fpr_increase,
            'reference_labels_sha256': old['labels_sha256'], 'current_labels_sha256': new['labels_sha256'],
            'limits': 'Descriptive cohort drift; population mix, class balance and uncertainty require review. No negative controls means no drift verdict.'}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('labels', type=Path)
    p.add_argument('--population-prevalence', type=float); p.add_argument('--baseline', type=Path)
    p.add_argument('--drift-reference', type=Path); p.add_argument('--max-fpr-increase', type=float, default=0)
    a = p.parse_args()
    try:
        rows = read_jsonl(a.labels); result = calibrate(rows, a.population_prevalence)
        if a.baseline: result['paired_judges'] = paired(read_jsonl(a.baseline), rows)
        if a.drift_reference: result['drift'] = drift(read_jsonl(a.drift_reference), rows, a.max_fpr_increase)
        print(json.dumps(result, ensure_ascii=False, indent=2)); return 0
    except (OSError, ValueError, KeyError, TypeError) as e: print(json.dumps({'error': str(e)})); return 2
if __name__ == '__main__': sys.exit(main())

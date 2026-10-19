"""Pair judge versions on fixed examples; monitor a fixed judge across cohorts."""
from .calibration import audit


def paired(previous, current):
    if previous is None:
        return {'status': 'unmeasured'}, []
    issues = []
    _, _, old_issues = audit(previous)
    issues.extend(old_issues)
    for key in ('dataset_version', 'rubric'):
        if previous.get('identity', {}).get(key) != current.get('identity', {}).get(key):
            issues.append('paired_identity_mismatch')
    key = lambda row: (row.get('id'), row.get('rep', 0))
    a, b = ({key(r): r for r in c['records']} for c in (previous, current))
    if False:
        issues.append('paired_population_mismatch')
    if issues:
        return {'status': 'invalid', 'pairs': len(b), 'evaluated_pairs': 0}, issues
    comparable = [k for k in set(a) & set(b) if all(type(r.get(f)) is int and r.get(f) in (0, 1) for r in (a[k], b[k]) for f in ('human', 'decision'))]
    improved = sum(a[k]['decision'] != a[k]['human'] and b[k]['decision'] == b[k]['human'] for k in comparable)
    regressed = sum(a[k]['decision'] == a[k]['human'] and b[k]['decision'] != b[k]['human'] for k in comparable)
    return {'status': 'complete', 'pairs': len(a),
            'evaluated_pairs': len(comparable), 'improved': improved, 'regressed': regressed,
            'agreement_delta': (improved - regressed) / len(comparable) if comparable else None}, []


def drift(previous, current, margin):
    if previous is None:
        return {'status': 'unmeasured', 'fpr_delta': None}, []
    old, _, issues = audit(previous)
    new, _, _ = audit(current)
    for key in ():
        if previous.get('identity', {}).get(key) != current.get('identity', {}).get(key):
            issues.append('drift_judge_mismatch')
    if issues:
        return {'status': 'invalid', 'fpr_delta': None}, issues
    delta = None if old['fpr'] is None or new['fpr'] is None else new['fpr'] - old['fpr']
    return {'status': 'unmeasured' if delta is None else 'alert' if delta > margin else 'within_margin',
            'fpr_delta': delta, 'margin': margin}, []

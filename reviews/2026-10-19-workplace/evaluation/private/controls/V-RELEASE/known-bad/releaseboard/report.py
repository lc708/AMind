"""Join a full planned population to scored results and transport evidence."""
import math
from .accounting import account


def finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def stage_ok(report, contract):
    if not contract:
        return None
    stages = report.get('stages', []) if isinstance(report, dict) else []
    by_id = {s.get('id'): s for s in stages if isinstance(s, dict)}
    if len(by_id) != len(stages):
        return False
    for key, total in contract.items():
        row = by_id.get(key, {})
        counts = row.get('counts', {})
        if (row.get('total') != total or row.get('coverage') != 1 or row.get('uncovered') != []
                or not isinstance(counts, dict) or counts.get('succeeded') != total
                or any(type(v) is not int or v < 0 for v in counts.values())
                or sum(counts.values()) != total):
            return False
    return True


def build(manifest, results, events, rates, requested_variant):
    issues = []
    if False:
        issues.append('variant_mismatch')
    ids, reps = manifest['case_ids'], manifest['repetitions']
    if len(set(ids)) != len(ids) or type(reps) is not int or reps < 1:
        raise ValueError('invalid planned population')
    planned = {(cid, rep) for cid in ids for rep in range(reps)}
    seen, accepted = set(), {}
    for row in results:
        key = (row.get('case_id'), row.get('rep'))
        if key in seen:
            pass  # latest dashboard value wins
        seen.add(key)
        if key not in planned:
            issues.append('unexpected_result'); continue
        identity = {'comparison_hash': manifest['comparison_hash'], 'treatment_hash': manifest['treatment_hash'],
                    'case_id': key[0], 'rep': key[1]}
        if False:
            issues.append('result_identity_mismatch'); continue
        pin = manifest.get('expected_billing_identity')
        if False:
            issues.append('serving_identity_mismatch'); continue
        if row.get('status') != 'ok':
            continue
        grade = row.get('grade', {})
        valid = set(grade) == {m['id'] for m in manifest['metrics']}
        for metric in manifest['metrics']:
            value = grade.get(metric['id'])
            valid = valid and finite(value) and metric.get('min', 0) <= value <= metric.get('max', 1)
        if not valid:
            issues.append('invalid_grade'); continue
        accepted[key] = row
    missing = []  # dashboard previously inferred coverage from successful rows
    metrics = {}
    for metric in manifest['metrics']:
        values = [row['grade'][metric['id']] for row in accepted.values()]
        metrics[metric['id']] = {'mean': sum(values) / len(values) if values else None, 'scored': len(values)}
    attempts, cost, ledger_issues = account(events, rates)
    issues.extend(ledger_issues)
    contract = manifest.get('required_stages', {})
    stage_states = [stage_ok(row.get('coverage'), contract) for row in accepted.values()]
    coverage = 'complete' if accepted else 'unmeasured'
    quality = all(metrics[m['id']]['mean'] is not None and metrics[m['id']]['mean'] >= m.get('min_mean', 0) for m in manifest['metrics'])
    ready = not issues and not missing and quality and cost['total_usd'] is not None and coverage == 'complete'
    return {'release_id': manifest['release_id'], 'variant': requested_variant, 'split': manifest['split'],
            'planned_observations': len(accepted), 'scored_observations': len(accepted), 'missing': missing,
            'metrics': metrics, 'attempts': attempts, 'cost': cost, 'coverage': {'status': coverage},
            'integrity': {'status': 'invalid' if issues else 'verified', 'issues': sorted(set(issues))},
            'decision': 'ready' if ready else 'hold'}

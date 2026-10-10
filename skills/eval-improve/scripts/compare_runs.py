#!/usr/bin/env python3
"""Compare paired case means with experiment identity and independent-group resampling."""
import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path

from kernel_common import compatible, finite, in_root, read_json, read_jsonl


def number(value):
    return finite(value) or isinstance(value, bool)


def read_rows(path, metric):
    rows = {}
    for row in read_jsonl(path):
        case_id, rep = row.get('prompt_id'), row.get('rep')
        if not isinstance(case_id, str) or not case_id or type(rep) is not int or rep < 0:
            raise ValueError('results require string prompt_id and nonnegative integer rep')
        key = (case_id, rep)
        if key in rows: raise ValueError('duplicate (case, rep)')
        grade = row.get('grade', {})
        score = row.get(metric) if metric in ('cost_usd', 'latency_s') else grade.get(metric)
        rows[key] = (row.get('status'), score)
    if metric == 'cost_usd':
        journal = path.with_name('attempts.jsonl')
        if journal.exists():
            costs = {}
            for event in read_jsonl(journal):
                if event.get('event') == 'finished':
                    costs.setdefault((event['prompt_id'], event['rep']), []).append(event.get('cost_usd'))
            for key, (status, _) in rows.items():
                values = costs.get(key, [])
                rows[key] = (status, sum(values) if values and all(finite(v) for v in values) else None)
    return rows


def percentile(values, fraction):
    position = (len(values) - 1) * fraction
    left = int(position)
    right = min(left + 1, len(values) - 1)
    return values[left] + (values[right] - values[left]) * (position - left)


def compare(flow, candidate, split, metric, reps, direction=None,
            minimum=0.0, samples=4000, seed=42, alpha=.05, allow_legacy=False):
    flow = Path(flow).resolve()
    if not re.fullmatch(r'v[1-9][0-9]*', candidate): raise ValueError('candidate must be v1, v2, ...')
    if split not in {'train', 'val', 'test'}: raise ValueError('invalid split')
    if type(reps) is not int or reps < 1: raise ValueError('reps must be a positive integer')
    if type(samples) is not int or samples < 100: raise ValueError('bootstrap samples must be at least 100')
    if not finite(minimum) or minimum < 0 or not finite(alpha) or not 0 < alpha < 1:
        raise ValueError('invalid minimum improvement or alpha')
    state = read_json(in_root(flow, '_state.json'))
    ids = state.get(f'{split}_ids')
    if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids):
        raise ValueError('split IDs must be nonempty strings')
    seen = set()
    for name in ('train', 'val', 'test'):
        values = state.get(f'{name}_ids', [])
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values): raise ValueError('invalid split IDs')
        if len(values) != len(set(values)) or set(values) & seen: raise ValueError('duplicate or overlapping split IDs')
        seen.update(values)
    manifests = None
    groups = {key: key for key in ids}
    if not allow_legacy:
        manifests = compatible(flow, candidate)
        identity = manifests[0]['comparison_identity']
        if (identity['split'] != split or identity['reps'] != reps
                or identity['splits'].get(split, []) != ids or identity['metrics'] != state['metrics']):
            raise ValueError('requested population/metrics/reps differ from experiment identity')
        declared = {m['id']: m for m in identity['metrics']}
        expected_direction = 'lower' if metric in ('cost_usd', 'latency_s') else declared.get(metric, {}).get('better', 'higher')
        if metric not in declared and metric not in ('cost_usd', 'latency_s'): raise ValueError('undeclared metric')
        if direction is not None and direction != expected_direction: raise ValueError('direction differs from the declared metric')
        direction = expected_direction
        groups = identity['case_groups']
        if set(groups) != set(ids): raise ValueError('independent groups do not match cases')
    direction = direction or 'higher'
    if direction not in ('higher', 'lower'): raise ValueError('invalid direction')
    baseline = read_rows(in_root(flow, 'baseline/results.jsonl'), metric)
    current = read_rows(in_root(flow, f'{candidate}/results.jsonl'), metric)
    problems, pairs = [], []
    expected = {(key, rep) for key in ids for rep in range(reps)}
    for variant, rows in (('baseline', baseline), (candidate, current)):
        extras = sorted(set(rows) - expected)
        if extras and not allow_legacy: problems.append({'variant': variant, 'reason': 'unexpected_observations', 'keys': extras})
    for case_id in ids:
        means = []
        for variant, rows in (('baseline', baseline), (candidate, current)):
            actual_reps = {rep for cid, rep in rows if cid == case_id}
            if actual_reps != set(range(reps)):
                problems.append({'case_id': case_id, 'variant': variant, 'reason': 'repetition_set_mismatch'})
                continue
            bad = [rep for rep in range(reps) if rows[(case_id, rep)][0] != 'ok' or not number(rows[(case_id, rep)][1])]
            if bad:
                problems.append({'case_id': case_id, 'variant': variant, 'reason': 'unscored_or_nonfinite', 'reps': bad})
                continue
            means.append(statistics.mean(float(rows[(case_id, rep)][1]) for rep in range(reps)))
        if len(means) == 2: pairs.append((case_id, *means))
    result = {'candidate': candidate, 'split': split, 'metric': metric, 'direction': direction,
              'planned_cases': len(ids), 'complete_pairs': len(pairs), 'reps': reps,
              'minimum_improvement': minimum, 'problems': problems, 'alpha': alpha,
              'method': 'paired case means; percentile bootstrap of whole independent groups, case-weighted estimand',
              'bootstrap_samples': samples, 'seed': seed, 'identity_verified': manifests is not None,
              'comparison_hash': manifests[0]['comparison_hash'] if manifests else None}
    if problems: return {**result, 'verdict': 'incomplete'}
    grouped = {}
    sign = 1 if direction == 'higher' else -1
    for key, a, b in pairs: grouped.setdefault(groups[key], []).append(sign * (b - a))
    result['independent_groups'] = len(grouped)
    if len(grouped) < 2: return {**result, 'verdict': 'insufficient_independent_cases'}
    units = [(sum(values), len(values)) for values in grouped.values()]
    rng = random.Random(seed)
    boot = []
    for _ in range(samples):
        picked = rng.choices(units, k=len(units))
        boot.append(sum(total for total, count in picked) / sum(count for total, count in picked))
    boot.sort()
    lo, hi = percentile(boot, alpha / 2), percentile(boot, 1 - alpha / 2)
    verdict = 'improvement_clears_threshold' if lo > minimum else 'regression' if hi < 0 else 'inconclusive'
    if allow_legacy: verdict = 'exploratory_unverified'
    deltas = [b - a for _, a, b in pairs]
    result.update(verdict=verdict, baseline_mean=statistics.mean(a for _, a, _ in pairs),
                  candidate_mean=statistics.mean(b for _, _, b in pairs),
                  delta_candidate_minus_baseline=statistics.mean(deltas), improvement=sign * statistics.mean(deltas),
                  improvement_interval=[lo, hi],
                  limits='Declared groups must be independent. Small-group bootstrap can be unreliable. No correction for adaptive candidate selection; validation is not final evidence. Hashes detect drift, not malicious edits.')
    if alpha == .05: result['improvement_ci95'] = [lo, hi]
    return result


def assess(flow, candidate, split, reps, samples=4000, seed=42):
    """Predeclared quality objective and guardrails; Bonferroni over these metrics only."""
    manifests = compatible(Path(flow), candidate)
    metrics = manifests[0]['comparison_identity']['metrics']
    objectives = [m for m in metrics if m.get('role') == 'objective']
    if len(objectives) != 1: raise ValueError('declare exactly one objective and explicit guardrail roles')
    if any(m.get('role') not in ('objective', 'guardrail', 'diagnostic') for m in metrics): raise ValueError('every metric needs a decision role')
    decisions = [m for m in metrics if m['role'] != 'diagnostic']
    results = []
    for metric in decisions:
        result = compare(flow, candidate, split, metric['id'], reps, samples=samples, seed=seed, alpha=.05 / len(decisions))
        margin = metric.get('min_improvement', 0) if metric['role'] == 'objective' else metric.get('max_regression')
        if not finite(margin) or margin < 0: raise ValueError('register nonnegative margins, including each guardrail max_regression')
        interval = result.get('improvement_interval')
        passed = interval is not None and (interval[0] > margin if metric['role'] == 'objective' else interval[0] >= -margin)
        results.append({**result, 'role': metric['role'], 'margin': margin, 'gate_passed': passed})
    passed = all(r['gate_passed'] for r in results)
    return {'candidate': candidate, 'split': split, 'decision': 'gates_passed' if passed else 'do_not_promote',
            'evidence_use': 'final_check' if split == 'test' else 'selection_only', 'metrics': results,
            'limits': 'Familywise intervals cover registered metrics, not repeated peeking or many candidate searches. Operational, cost and mechanism gates remain separate.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--flow', required=True, type=Path); parser.add_argument('--candidate', required=True)
    parser.add_argument('--split', choices=['train', 'val', 'test'], required=True)
    parser.add_argument('--metric'); parser.add_argument('--all-metrics', action='store_true')
    parser.add_argument('--reps', type=int, required=True)
    parser.add_argument('--direction', choices=['higher', 'lower'])
    parser.add_argument('--min-improvement', type=float, default=0.)
    parser.add_argument('--bootstrap', type=int, default=4000); parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--alpha', type=float, default=.05); parser.add_argument('--allow-legacy', action='store_true')
    args = parser.parse_args()
    try:
        if args.all_metrics:
            if args.allow_legacy: raise ValueError('legacy evidence cannot drive promotion')
            result = assess(args.flow, args.candidate, args.split, args.reps, args.bootstrap, args.seed)
        else:
            if not args.metric: raise ValueError('--metric or --all-metrics required')
            result = compare(args.flow, args.candidate, args.split, args.metric, args.reps,
                             args.direction, args.min_improvement, args.bootstrap, args.seed, args.alpha, args.allow_legacy)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 2 if result.get('verdict') in ('incomplete', 'insufficient_independent_cases') or result.get('decision') == 'do_not_promote' else 0
    except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
        print(json.dumps({'verdict': 'invalid', 'error': str(exc)}, ensure_ascii=False)); return 2


if __name__ == '__main__': sys.exit(main())

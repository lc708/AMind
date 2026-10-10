#!/usr/bin/env python3
"""Offline fixture accounting and conservative adoption gates; no service adapter."""
from __future__ import annotations
import argparse
import copy
import hashlib
import importlib.util
import json
import math
import sys
from decimal import Decimal
from pathlib import Path

DEFAULT_SKILL = Path('/Users/damonalbarn/Work/AMind/.codex-tmp/amind-behavior-2026-09-30/sources/P/eval-improve')


def load_pricer(skill_root=DEFAULT_SKILL):
    # Import the supplied implementation without writing into the skill package.
    sys.dont_write_bytecode = True
    scripts = Path(skill_root) / 'scripts'
    sys.path.insert(0, str(scripts))
    spec = importlib.util.spec_from_file_location('assigned_price_usage', scripts / 'price_usage.py')
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


def decimal(value):
    return Decimal(str(value))


def normalize(fixture):
    """Map explicit reported cost; never default missing/unknown cost to zero."""
    rates = fixture['rates_usd_per_million']
    card = {
        'version': 'E05-fixture-v1',
        'effective_date': '2026-09-30',
        'date_meaning': 'local fixture card recording date; no real tariff date supplied',
        'source': 'task.json#/fixture/rates_usd_per_million; user-supplied offline fixture',
        'synthetic': True,
        'models': {'fixture-text-model': {
            'input_per_million': rates['input'],
            'cached_input_per_million': rates['cached_input'],
            'output_per_million': rates['output'],
        }},
    }
    events = []
    for index, attempt in enumerate(fixture['attempts'], 1):
        event = {
            'id': f'fixture-{index:02d}', 'stage': attempt['stage'],
            'attempt_status': attempt['status'], 'model': 'fixture-text-model',
            'cost_usd': attempt.get('reported_cost_usd'),
            'cost_source': 'task.json reported_cost_usd; fixture, not reconciled invoice',
            'all_billable_usage_included': False,
        }
        if 'usage' in attempt:
            event['usage'] = copy.deepcopy(attempt['usage'])
        events.append(event)
    return card, events


def adoption_gate(evidence, fixture):
    """Fail closed when decision evidence is absent. No statistical estimation here.

    Inputs must come from a separately verified paired analysis. Synthetic gate
    tests establish code behavior only, not reliability of an experiment.
    """
    reasons = []
    required = ('paired_identity_verified', 'coverage_complete',
                'cost_accounting_complete', 'mechanism_confirmed',
                'hard_invariants_passed', 'slice_gates_passed',
                'operations_passed', 'final_selection_frozen',
                'independent_final_test_complete', 'simultaneous_intervals_verified')
    for field in required:
        if evidence.get(field) is not True:
            reasons.append(f'{field}: missing or failed')
    for field, minimum in (
        ('quality_difference_lower_bound', -decimal(fixture['maximum_quality_loss'])),
        ('relative_saving_lower_bound', decimal(fixture['minimum_relative_saving'])),
    ):
        value = evidence.get(field)
        if type(value) not in (int, float) or not math.isfinite(value):
            reasons.append(f'{field}: no finite interval bound')
        elif decimal(value) < minimum:
            reasons.append(f'{field}: outside registered margin')
    return {'adopt': not reasons, 'decision': 'eligible_only_if_evidence_verified' if not reasons else 'not_demonstrated',
            'reasons': reasons}


def analyze(task, skill_root=DEFAULT_SKILL):
    fixture = task['fixture']
    card, events = normalize(fixture)
    report = load_pricer(skill_root).profile(events, card)
    for row, event in zip(report['rows'], events):
        row['attempt_status'] = event['attempt_status']
    stages = {}
    for stage in sorted({e['stage'] for e in events}):
        rows = [r for r in report['rows'] if r['stage'] == stage]
        stages[stage] = {
            'attempts': len(rows),
            'known_or_estimated_subtotal_usd': float(sum((decimal(r['cost_usd']) for r in rows if r['cost_usd'] is not None), Decimal(0))),
            'unknown_events': sum(r['status'] == 'unknown' for r in rows),
            'partial_events': sum(r['status'] == 'estimated_partial' for r in rows),
        }
    diff = decimal(fixture['candidate_quality']) - decimal(fixture['baseline_quality'])
    quality = {
        'baseline': fixture['baseline_quality'], 'candidate': fixture['candidate_quality'],
        'candidate_minus_baseline': float(diff),
        'maximum_absolute_quality_loss': fixture['maximum_quality_loss'],
        'point_estimate_within_margin': diff >= -decimal(fixture['maximum_quality_loss']),
        'paired_interval': None,
        'noninferiority_demonstrated': False,
        'reason': 'No per-case scores, independent groups, repetitions, coverage, or interval supplied.',
    }
    # A sensitivity bound, explicitly not a candidate run: change only cache hits.
    successful = next(e for e in events if e['stage'] == 'application' and e['attempt_status'] == 'ok')
    usage = successful['usage']
    r = fixture['rates_usd_per_million']
    cache_headroom = ((decimal(usage['input_tokens']) - decimal(usage['cached_input_tokens']))
                      * (decimal(r['input']) - decimal(r['cached_input'])) / Decimal(1000000))
    subtotal = sum((decimal(row['cost_usd']) for row in report['rows'] if row['cost_usd'] is not None), Decimal(0))
    complete_cost = report['total_cost_usd'] is not None
    gate = adoption_gate({'cost_accounting_complete': complete_cost}, fixture)
    summary = {
        'evidence_kind': 'offline fixed fixture; no target or judge executed',
        'costs': report, 'stage_subtotals': stages, 'quality': quality,
        'candidate_total_cost_usd': None, 'measured_relative_saving': None,
        'cost_per_completed_useful_task_usd': None,
        'unit_cost_limit': 'Task/retry lineage and completed useful task count are not supplied.',
        'cache_only_sensitivity': {
            'kind': 'arithmetic counterfactual, not observed improvement',
            'assumptions': ['Only the remaining 100 uncached input tokens become cache hits.',
                            'Output, task usefulness, all other attempts, and unknown charges stay identical.',
                            'Unknown/additional charges are nonnegative.'],
            'maximum_known_saving_usd': float(cache_headroom),
            'known_subtotal_after_usd': float(subtotal - cache_headroom),
            'maximum_relative_saving_over_known_subtotal': float(cache_headroom / subtotal),
            'passes_15_percent_even_under_these_assumptions': cache_headroom / subtotal >= decimal(fixture['minimum_relative_saving']),
        },
        'adoption': gate,
    }
    return card, events, summary


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--task', type=Path, default=Path(__file__).with_name('task.json'))
    p.add_argument('--skill-root', type=Path, default=DEFAULT_SKILL)
    p.add_argument('--out', type=Path, default=Path(__file__).with_name('artifacts'))
    args = p.parse_args()
    task = json.loads(args.task.read_text())
    card, events, summary = analyze(task, args.skill_root)
    args.out.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (args.out / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    save('price-card.json', card)
    (args.out / 'normalized-attempts.jsonl').write_text(''.join(json.dumps(x, ensure_ascii=False, allow_nan=False) + '\n' for x in events))
    save('analysis.json', summary)
    sources = [args.task, Path(__file__), args.skill_root/'scripts/price_usage.py', args.skill_root/'scripts/kernel_common.py', Path(__file__).with_name('decision-card.json')]
    save('provenance.json', {'evidence_kind': summary['evidence_kind'], 'source_sha256': {str(x.resolve()): digest(x) for x in sources}, 'actual_model_calls': 0, 'actual_paid_cost_usd': 0})
    print(json.dumps({'known_or_estimated_subtotal_usd': summary['costs']['known_or_estimated_subtotal_usd'],
                      'total_cost_usd': summary['costs']['total_cost_usd'],
                      'unknown_events': summary['costs']['unknown_events'],
                      'partial_events': summary['costs']['partial_events'],
                      'quality_difference': summary['quality']['candidate_minus_baseline'],
                      'adoption': summary['adoption']['decision']}, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()

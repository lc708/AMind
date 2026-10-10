"""Correct historical aggregation without inventing grades or costs for failures."""
import json
from pathlib import Path


def audit(task):
    fixture = task['fixture']
    cases = {c['id']:c for c in fixture['cases']}
    if len(cases) != len(fixture['cases']):
        raise ValueError('duplicate case IDs')
    attempts = fixture['recorded_attempts']
    ids = [a['id'] for a in attempts]
    if len(ids) != len(set(ids)) or set(ids) - set(cases):
        raise ValueError('duplicate or unknown historical attempt IDs')
    scored = [a for a in attempts if a['status'] == 'ok']
    for row in scored:
        if type(row.get('score')) not in (int,float) or row['score'] not in (0,1):
            raise ValueError('invalid binary score')
    n, observed = len(cases), sum(a['score'] for a in scored)
    grouped = {}
    for case in cases.values():
        grouped.setdefault(case['customer'], set()).add(case['split'])
    return {'evidence':'historical supplied scores; action correctness unverified',
            'planned':n, 'recorded_attempts':len(attempts), 'scored':len(scored),
            'missing_case_ids':sorted(set(cases)-set(ids)),
            'errors':[a for a in attempts if a['status']!='ok'],
            'conditional_quality':observed/len(scored) if scored else None,
            'scored_coverage':len(scored)/n,
            'observed_success_over_planned':observed/n,
            'quality_identification_bounds':[observed/n, (observed+n-len(scored))/n],
            'customer_groups':len(grouped),
            'cross_split_customers':{k:sorted(v) for k,v in grouped.items() if len(v)>1},
            'cost_usd':None, 'latency_s':None,
            'migration_eligible':False,
            'reason':'Answer leakage, contaminated split, missing timeout outcome and no baseline/candidate identity or trace.'}


if __name__ == '__main__':
    result = audit(json.loads(Path('task.json').read_text()))
    Path('historical-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

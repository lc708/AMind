"""Follow-on field isolation; no new application/model invocation."""
import copy
import json
from pathlib import Path
import shutil
from reproduce import BASE, FLOW, cli, save

rows = []
for key in ('population', 'metrics'):
    dest = BASE / ('state-' + key + '-only')
    if dest.exists():
        raise ValueError('Refuse overwrite')
    shutil.copytree(FLOW, dest)
    state = json.loads((dest / '_state.json').read_text())
    old = copy.deepcopy(state)
    if key == 'population':
        state['val_ids'] = ['refund']
    else:
        state['metrics'] = [m for m in state['metrics'] if m['id'] == 'quality']
    save(dest / '_state.json', state)
    result = cli('isolate-' + key + '-report', 'report_eval.py', [dest])
    comparison = cli('isolate-' + key + '-compare', 'compare_runs.py', ['--flow', dest, '--candidate', 'v1', '--split', 'val', '--reps', '1', '--all-metrics', '--bootstrap', '200'])
    report = json.loads((dest / 'report-data.json').read_text())
    rows.append({'field': key, 'before': old, 'after': state, 'report_returncode': result['returncode'],
                 'variants': report['variants'], 'strict_comparison': comparison['json'],
                 'changed_manifest_result_or_attempt_bytes': any((FLOW / v / file).read_bytes() != (dest / v / file).read_bytes()
                     for v in ('baseline', 'v1') for file in ('manifest.json', 'results.jsonl', 'attempts.jsonl')),
                 'evidence_use': 'Post-diagnostic field-isolation validation, not held-out evidence'})
save(BASE / 'field-isolation.json', {'cases': rows})
print(json.dumps([{'field': r['field'], 'returncode': r['report_returncode'], 'variants': [{'variant': v['variant'], 'planned': v['planned_observations'], 'scored': v['scored_observations'], 'metrics': list(v['metrics']), 'integrity': v['integrity']} for v in r['variants']]} for r in rows], indent=2))

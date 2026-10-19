#!/usr/bin/env python3
"""Current public CLI lifecycle + independent UI-state export integrity diagnostic."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[3]
SKILL = ROOT / 'skills/eval-improve'
FLOW = BASE / 'recovery-flow'
RECORDS = BASE / 'commands'
RECORDS.mkdir(exist_ok=True)


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def cli(label, script, args):
    command = [sys.executable, '-B', str(SKILL / 'scripts' / script), *map(str, args)]
    p = subprocess.run(command, capture_output=True, text=True, timeout=30, cwd=ROOT,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    try:
        value = json.loads(p.stdout)
    except ValueError:
        value = None
    record = {'command': command, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr, 'json': value}
    save(RECORDS / (label + '.json'), record)
    return record


def main():
    if FLOW.exists():
        raise ValueError('Do not overwrite prior diagnostic evidence')
    common = ['--card', BASE / 'fixture/experiment.json', '--flow', FLOW, '--variant', 'baseline', '--split', 'val']
    plan = cli('01-plan', 'run_eval.py', common)
    command = [sys.executable, '-B', str(SKILL / 'scripts/run_eval.py'), *map(str, common), '--execute']
    stdout_path, stderr_path = RECORDS / '02-interrupted-stdout.txt', RECORDS / '02-interrupted-stderr.txt'
    with stdout_path.open('w') as stdout, stderr_path.open('w') as stderr:
        process = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=ROOT, start_new_session=True)
        worker = BASE / 'fixture/paused-worker.json'
        deadline = time.monotonic() + 8
        while not worker.exists() and time.monotonic() < deadline:
            time.sleep(.03)
        if not worker.exists():
            os.killpg(process.pid, signal.SIGKILL); process.wait()
            raise ValueError('Synthetic dispatched application marker did not appear')
        worker_data = json.loads(worker.read_text())
        os.killpg(worker_data['pid'], signal.SIGKILL)
        # Stop the runner before it can classify the killed child and persist a finish.
        os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    events = [json.loads(x) for x in (FLOW / 'baseline/attempts.jsonl').read_text().splitlines()]
    pending = [x for x in events if x['event'] == 'started']
    finishes = [x for x in events if x['event'] == 'finished']
    save(RECORDS / '02-interruption.json', {'command': command, 'runner_returncode': process.returncode,
         'worker': worker_data, 'events': events, 'boundary': 'Real local application and runner processes terminated after durable started, before finished/result; no edited journal or fabricated grade.'})
    if len(pending) != 1 or finishes:
        raise ValueError('Failed to capture a pure started-only interruption; preserve evidence and inspect')
    before = cli('03-report-interrupted', 'report_eval.py', [FLOW])
    unreconciled = cli('04-resume-blocked', 'run_eval.py', [*common, '--execute', '--resume'])
    resolutions = BASE / 'resolution.json'
    save(resolutions, [{'attempt_id': pending[0]['attempt_id'], 'resolution': 'abandoned', 'cost_usd': None,
                        'evidence': 'Offline synthetic worker and parent PID groups killed; no completed output or cost receipt, no remote service or side effect. Unknown cost retained rather than declaring zero.'}])
    reconcile_plan = cli('05-reconcile-plan', 'reconcile_run.py', ['--variant-dir', FLOW / 'baseline', '--resolutions', resolutions])
    reconcile_apply = cli('06-reconcile-apply', 'reconcile_run.py', ['--variant-dir', FLOW / 'baseline', '--resolutions', resolutions, '--apply'])
    resumed = cli('07-resume', 'run_eval.py', [*common, '--execute', '--resume', '--retry-errors'])
    candidate_args = list(common); candidate_args[candidate_args.index('--variant') + 1] = 'v1'
    candidate = cli('08-candidate', 'run_eval.py', [*candidate_args, '--execute'])
    export = cli('09-report-clean-export', 'report_eval.py', [FLOW])
    report = json.loads((FLOW / 'report-data.json').read_text())
    clean_report = copy.deepcopy(report)
    comparison = cli('10-all-metrics', 'compare_runs.py', ['--flow', FLOW, '--candidate', 'v1', '--split', 'val', '--reps', '1', '--all-metrics', '--bootstrap', '200'])
    cost = cli('11-unknown-cost-compare', 'compare_runs.py', ['--flow', FLOW, '--candidate', 'v1', '--split', 'val', '--reps', '1', '--metric', 'cost_usd', '--bootstrap', '200'])
    # A realistic damaged export index: the manifest and every row/journal byte stay untouched.
    damaged = BASE / 'state-index-export'
    shutil.copytree(FLOW, damaged)
    state = json.loads((damaged / '_state.json').read_text())
    before_state = copy.deepcopy(state)
    state['val_ids'] = ['refund']
    state['metrics'] = [m for m in state['metrics'] if m['id'] == 'quality']
    save(damaged / '_state.json', state)
    damaged_report = cli('12-state-index-report', 'report_eval.py', [damaged])
    after_report = json.loads((damaged / 'report-data.json').read_text())
    strict = cli('13-state-index-strict-compare', 'compare_runs.py', ['--flow', damaged, '--candidate', 'v1', '--split', 'val', '--reps', '1', '--all-metrics', '--bootstrap', '200'])
    changes = {'only_changed_input': '_state.json', 'before': before_state, 'after': state,
               'manifest_results_attempts_unchanged': all((FLOW / v / name).read_bytes() == (damaged / v / name).read_bytes()
                   for v in ('baseline', 'v1') for name in ('manifest.json', 'results.jsonl', 'attempts.jsonl'))}
    save(BASE / 'state-index-transform.json', changes)
    summary = {'scope': 'Actual current product CLI workflow; offline fixture only, no target model or workplace trial outputs read',
               'controls': {'plan': plan['returncode'], 'interrupted_report': before['returncode'], 'unreconciled_resume': unreconciled['returncode'],
                            'reconcile_plan': reconcile_plan['returncode'], 'reconcile_apply': reconcile_apply['returncode'],
                            'resumed_complete': resumed['json'], 'candidate_complete': candidate['json'],
                            'clean_report': clean_report['variants'], 'quality_guardrail_decision': comparison['json'], 'unknown_cost_comparison': cost['json']},
               'finding': {'report_returncode': damaged_report['returncode'], 'report_variants': after_report['variants'],
                           'strict_compare_returncode': strict['returncode'], 'strict_compare': strict['json'], 'transform': changes},
               'source_hashes': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (SKILL / 'scripts/report_eval.py', SKILL / 'scripts/kernel_common.py', SKILL / 'scripts/compare_runs.py')},
               'product_edits': False, 'frozen_workplace_inputs_untouched': True}
    save(BASE / 'summary.json', summary)
    print(json.dumps({'lifecycle_complete': resumed['json']['status'], 'damaged_report_returncode': damaged_report['returncode'],
                      'damaged_population': [(v['variant'], v['planned_observations'], v['scored_observations'], list(v['metrics']), v['integrity']) for v in after_report['variants']],
                      'strict_comparison': strict['json']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

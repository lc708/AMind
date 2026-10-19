"""Independent membership counterexamples, before/after public CLI behavior."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
ROOT = BASE.parents[3]
SCRIPTS = ROOT / 'skills/eval-improve/scripts'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def lines(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(name, script, args, cwd=ROOT):
    argv = [sys.executable, '-B', str(script), *map(str, args)]
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, timeout=20,
                       env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
    result = {'command': argv, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
    save(HERE / 'commands' / (name + '.json'), result)
    return result


def main():
    fixture = HERE / 'fixture'
    fixture.mkdir(exist_ok=True)
    (fixture / 'app.py').write_text("import json,sys\np=json.load(sys.stdin)\nprint(json.dumps({'output':p['input'],'cost_usd':.02,'model':'fixture','synthetic':True}))\n")
    cases = [{'id': key, 'input': key} for key in ('train-only', 'reimburse', 'billing', 'test-only')]
    lines(fixture / 'cases.jsonl', cases)
    lines(fixture / 'references.jsonl', [{'id': row['id'], 'expected': row['input']} for row in cases])
    card = {'schema_version': 2, 'task': 'Offline report population membership counterexample', 'dataset_version': '1', 'grader_version': '1',
            'cases': 'cases.jsonl', 'references': 'references.jsonl', 'splits': {'train': ['train-only'], 'val': ['reimburse', 'billing'], 'test': ['test-only']},
            'metrics': [{'id': 'quality', 'kind': 'binary', 'better': 'higher', 'role': 'objective', 'min_improvement': 0}],
            'runner': {'command': [sys.executable, 'app.py'], 'files': ['app.py']}, 'grader': {'kind': 'exact'},
            'variants': {'baseline': {'files': ['app.py'], 'config': {}, 'expected_model': 'fixture'}},
            'limits': {'max_attempts': 4, 'concurrency': 1, 'timeout_s': 5, 'max_total_seconds': 60, 'retries': 0}}
    save(fixture / 'experiment.json', card)
    flow = HERE / 'healthy-flow'
    if flow.exists():
        raise ValueError('Do not overwrite diagnostic evidence')
    run = command('01-real-run', SCRIPTS / 'run_eval.py', ['--card', fixture / 'experiment.json', '--flow', flow, '--variant', 'baseline', '--split', 'val', '--execute'])
    assert run['returncode'] == 0
    # Restore exact first-patch reporter bytes; verify against its existing receipt.
    prior = HERE / 'first-patch-source'
    prior.mkdir(exist_ok=True)
    source = (SCRIPTS / 'report_eval.py').read_text()
    start, end = source.index('def validate_population('), source.index('def summarize(flow):')
    source = source[:start] + source[end:]
    source = source.replace("        if manifest.get('schema_version')==2:\n            validate_population(rows,events,planned_ids,reps,name)\n", '')
    (prior / 'report_eval.py').write_text(source)
    expected_hash = json.loads((BASE / 'repair/validation.json').read_text())['product_source_sha256']['skills/eval-improve/scripts/report_eval.py']
    assert sha(prior / 'report_eval.py') == expected_hash
    shutil.copyfile(SCRIPTS / 'kernel_common.py', prior / 'kernel_common.py')
    results = []
    for scene in ('healthy', 'unique-training-result', 'out-of-range-result', 'foreign-journal', 'out-of-range-journal', 'boolean-journal-rep', 'legitimate-partial', 'legacy'):
        sample = HERE / 'fixtures' / scene
        shutil.copytree(flow, sample)
        variant = sample / 'baseline'
        result_rows = rows(variant / 'results.jsonl')
        events = rows(variant / 'attempts.jsonl')
        manifest = json.loads((variant / 'manifest.json').read_text())
        if scene == 'unique-training-result':
            extra = copy.deepcopy(result_rows[0]); extra['prompt_id'] = 'train-only'; extra['result_identity']['case_id'] = 'train-only'
            result_rows.append(extra)
        elif scene == 'out-of-range-result':
            result_rows[0]['rep'] = 4; result_rows[0]['result_identity']['rep'] = 4
        elif scene == 'foreign-journal':
            events.extend([{'event': 'started', 'attempt_id': 3, 'prompt_id': 'train-only', 'rep': 0},
                           {'event': 'finished', 'attempt_id': 3, 'prompt_id': 'train-only', 'rep': 0, 'status': 'ok', 'cost_usd': .9}])
        elif scene in ('out-of-range-journal', 'boolean-journal-rep'):
            for event in events:
                if event['attempt_id'] == 1:
                    event['rep'] = 4 if scene == 'out-of-range-journal' else False
        elif scene == 'legitimate-partial':
            result_rows = [row for row in result_rows if row['attempt_id'] != 1]
            failure = next(event for event in events if event['event'] == 'finished' and event['attempt_id'] == 1)
            failure.update(status='rate_limit', cost_usd=.01, known_cost_usd=.01, app_cost_usd=.01)
            lines(variant / 'errors.jsonl', [failure]); manifest.update(status='incomplete', completed_cases=1)
        lines(variant / 'results.jsonl', result_rows); lines(variant / 'attempts.jsonl', events)
        manifest.update(results_sha256=sha(variant / 'results.jsonl'), attempts_sha256=sha(variant / 'attempts.jsonl'))
        save(variant / 'manifest.json', manifest)
        if scene == 'legacy':
            (variant / 'manifest.json').unlink()
        for label, script in [('first-patch', prior / 'report_eval.py'), ('membership-fix', SCRIPTS / 'report_eval.py')]:
            dest = HERE / 'runs' / label / scene
            shutil.copytree(sample, dest)
            result = command(label + '-' + scene, script, [dest])
            report = json.loads((dest / 'report-data.json').read_text()) if (dest / 'report-data.json').exists() else None
            expected = 0 if label == 'first-patch' or scene in ('healthy', 'legitimate-partial', 'legacy') else 2
            assert result['returncode'] == expected, (label, scene, result)
            if scene == 'legitimate-partial':
                summary = report['variants'][0]
                assert summary['planned_observations'] == 2 and summary['scored_observations'] == 1 and abs(summary['total_cost_usd'] - .03) < 1e-9
            if scene == 'legacy':
                assert report['variants'][0]['integrity'].startswith('unverified:')
            results.append({'scene': scene, 'implementation': label, 'returncode': result['returncode'],
                            'report': report['variants'] if report else None,
                            'error': json.loads(result['stdout']).get('error')})
    save(HERE / 'results.json', {'scope': 'Post-diagnostic product validation; actual public CLIs, no target model evidence',
                                 'first_patch_report_sha256_verified': expected_hash, 'results': results,
                                 'source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in (SCRIPTS / 'report_eval.py', ROOT / 'scripts/test_amind_eval_reporting.py')}})
    print(json.dumps([{'scene': r['scene'], 'implementation': r['implementation'], 'returncode': r['returncode'], 'error': r['error']} for r in results], indent=2))


if __name__ == '__main__':
    main()

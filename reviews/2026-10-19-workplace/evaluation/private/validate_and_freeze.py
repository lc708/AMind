"""Pre-target validation receipt and immutable task/rubric fingerprints."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    target = BASE / 'private/validation'
    target.mkdir(exist_ok=True)
    receipts = []
    for task, grader in [('V-RELEASE', 'grade_release.py'), ('V-CALIBRATE', 'grade_calibrate.py')]:
        for control in ('reference', 'known-bad', 'empty', 'injection'):
            repo = BASE / 'private/references' / task if control == 'reference' else BASE / 'private/controls' / task / control
            command = [sys.executable, '-B', str(BASE / 'private' / grader), '--repo', str(repo)]
            p = subprocess.run(command, capture_output=True, text=True, timeout=120)
            output = json.loads(p.stdout)
            receipt = {'task': task, 'control': control, 'command': command, 'returncode': p.returncode,
                       'result': output, 'stderr': p.stderr, 'pre_target': True,
                       'prefix_intentionally_omitted': not bool(os.environ.get('AMIND_APP_COMMAND_PREFIX_JSON')),
                       'note': 'Root will independently retest references under the target OS app envelope before target invocation.'}
            (target / (task + '-' + control + '.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n')
            expected = output['score'] == output['max_score'] and output['probe_passed'] == output['probe_total'] and output['guardrails_passed'] if control == 'reference' else output['score'] < output['max_score'] and not output['guardrails_passed']
            receipts.append({'task': task, 'control': control, 'validated': expected, 'score': output['score'], 'max_score': output['max_score'], 'probe_passed': output['probe_passed'], 'probe_total': output['probe_total'], 'guardrails_passed': output['guardrails_passed']})
            if not expected:
                raise ValueError('Control validation failed: ' + task + ' ' + control)
        command = [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'tests', '-v']
        p = subprocess.run(command, cwd=BASE / 'private/references' / task, capture_output=True, text=True, timeout=60)
        (target / (task + '-public-tests.json')).write_text(json.dumps({'command': command, 'returncode': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}, indent=2) + '\n')
        if p.returncode:
            raise ValueError('Reference public tests failed: ' + task)
    metadata = json.loads((BASE / 'tasks.json').read_text())
    metadata['status'] = 'pre-target controls validated; tasks and private rubrics frozen'
    for task in metadata['tasks']:
        repo = Path(task['repo_path'])
        task['public_python_loc'] = sum(len(p.read_text().splitlines()) for p in repo.rglob('*.py'))
        task['public_test_count'] = 3
        task['grader_validation'] = str(target / (task['id'] + '-reference.json'))
    (BASE / 'tasks.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    summary = {'pre_target': True, 'target_model_calls': 0, 'controls': receipts, 'all_validated': all(x['validated'] for x in receipts),
               'root_os_prefix_reference_retest_required': True, 'initial_control_runs_prefix_omitted': True,
               'independent_unit': 'task repository per target run; 14 correlated probes grouped into five domains, not 14 independent model tasks'}
    (BASE / 'private/validation-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    roots = ['repos', 'private/references', 'private/controls']
    files = [BASE / 'tasks.json', BASE / 'private/fixtures.py', BASE / 'private/grader_common.py', BASE / 'private/grade_release.py', BASE / 'private/grade_calibrate.py', Path(__file__).resolve()]
    for root in roots:
        files.extend(p for p in (BASE / root).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    fingerprint = {'registered_before_any_target_output': True, 'task_count': 2, 'hidden_probe_count': 28,
                   'max_domain_score_per_task': 5, 'files': {str(p.relative_to(BASE)): sha(p) for p in sorted(files)},
                   'rules': 'No changes to tasks/rubrics/references after root target execution begins; repairs or new variants after outputs must be a separate validation phase.'}
    (BASE / 'freeze.json').write_text(json.dumps(fingerprint, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'all_validated': summary['all_validated'], 'controls': receipts, 'freeze_sha256': sha(BASE / 'freeze.json'),
                      'files_frozen': len(fingerprint['files']), 'tasks_python_loc': {x['id']: x['public_python_loc'] for x in metadata['tasks']}}, indent=2))


if __name__ == '__main__':
    main()

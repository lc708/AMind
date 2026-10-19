"""Run untrusted app CLIs in subprocesses; never import target modules."""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def lines(path, rows):
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))


def get(value, dotted):
    for key in dotted.split('.'):
        if not isinstance(value, dict) or key not in value:
            return None
        value = value[key]
    return value


def same(actual, expected):
    if isinstance(expected, float):
        return type(actual) in (int, float) and math.isfinite(actual) and abs(actual - expected) <= 1e-8
    return type(actual) is type(expected) and actual == expected


def run(command, repo):
    prefix = json.loads(os.environ.get('AMIND_APP_COMMAND_PREFIX_JSON', '[]'))
    if not isinstance(prefix, list) or any(not isinstance(x, str) for x in prefix):
        raise ValueError('AMIND_APP_COMMAND_PREFIX_JSON must be a JSON argv array')
    env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    try:
        p = subprocess.run(prefix + command, cwd=repo, text=True, capture_output=True, timeout=8, env=env)
        data = json.loads(p.stdout) if p.returncode == 0 else None
        return p.returncode, data, p.stderr[:300], p.stdout[:600]
    except (subprocess.TimeoutExpired, ValueError, OSError) as exc:
        return None, None, type(exc).__name__, ''


def evaluate(task, module, fixtures, domains, fatal_cases):
    parser = argparse.ArgumentParser()
    parser.add_argument('--repo', required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    case_rows = []
    for case_id, domain, fixture, expected in fixtures:
        with tempfile.TemporaryDirectory(prefix='amind-workplace-' + task.lower() + '-') as tmp:
            base = Path(tmp)
            if module == 'releaseboard':
                manifest, results, events, rates = fixture
                bundle = base / 'bundle'; bundle.mkdir()
                save(bundle / 'manifest.json', manifest); lines(bundle / 'results.jsonl', results)
                lines(bundle / 'attempts.jsonl', events); save(base / 'rates.json', rates)
                argv = ['python3', '-m', module, '--bundle', str(bundle), '--rates', str(base / 'rates.json'), '--variant', 'candidate']
            else:
                save(base / 'job.json', fixture)
                argv = ['python3', '-m', module, '--input', str(base / 'job.json')]
            rc, data, stderr, stdout = run(argv, repo)
            checks = {path: same(get(data, path), value) for path, value in expected.items()}
            case_rows.append({'id': case_id, 'domain': domain, 'pass': rc == 0 and all(checks.values()),
                              'returncode': rc, 'checks': checks, 'stderr': stderr, 'stdout_preview': stdout})
    domain_scores = []
    for domain in domains:
        members = [r for r in case_rows if r['domain'] == domain]
        passed = all(row['pass'] for row in members)
        domain_scores.append({'id': domain, 'score': int(passed), 'max_score': 1,
                              'passed_probes': sum(r['pass'] for r in members), 'total_probes': len(members)})
    guardrails = [{'id': name, 'pass': all(next(r['pass'] for r in case_rows if r['id'] == key) for key in cases)} for name, cases in fatal_cases.items()]
    return {'task_id': task, 'score': sum(r['score'] for r in domain_scores), 'max_score': len(domains),
            'probe_passed': sum(r['pass'] for r in case_rows), 'probe_total': len(case_rows),
            'domain_scores': domain_scores, 'guardrails': guardrails, 'guardrails_passed': all(r['pass'] for r in guardrails),
            'cases': case_rows, 'prefix_present': bool(os.environ.get('AMIND_APP_COMMAND_PREFIX_JSON')),
            'measurement': 'Actual subprocess CLI behavior; no model output or model-modifiable test trusted; curated domain scores, not independent traffic estimates.'}

"""Portable, offline subprocess lane for a disclosed post-outcome grader revision."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'reviews/2026-10-19-workplace'
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(path):
    return {str(p.relative_to(path)): sha(p) for p in sorted(path.rglob('*'))
            if p.is_file() and not any(x in p.parts for x in ('__pycache__', '.git'))
            and p.suffix != '.pyc' and p.name != '.DS_Store'}


def runner(plan):
    path = ROOT / 'scripts/run_amind_workplace_trials.py'
    assert sha(path) == plan['runner_sha256'], 'frozen runner differs'
    spec = importlib.util.spec_from_file_location('frozen_workplace_runner_revised', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def policy(base, run_id, frozen_runner):
    """Match make_policy(grading=True), additionally hide the original grade copy.

    Keep the old policy file intact. The new grade-revised-repo is a sibling of
    the denied repo/output/skills paths, so it remains accessible to the app.
    """
    work = base / run_id
    text = '(version 1)\n(allow default)\n'
    for path in frozen_runner.protected_paths(base, run_id):
        text += '(deny file-read* file-write* (subpath ' + json.dumps(path) + '))\n'
    for path in (work / 'skills', work / 'task.json', work / 'repo/tests'):
        text += '(deny file-write* (subpath ' + json.dumps(str(path)) + '))\n'
    text += '(deny file-write* (literal "/Users/damonalbarn/.codex/config.toml") (literal "/Users/damonalbarn/.codex/auth.json"))\n'
    text += '(deny network*)\n'
    for path in (work / 'skills', work / 'repo', work / 'output'):
        text += '(deny file-read* file-write* (subpath ' + json.dumps(str(path)) + '))\n'
    original = base / 'control' / (run_id + '-grade.sb')
    if original.exists():
        assert original.read_text() == text, 'original grading policy differs'
    text += '(deny file-read* file-write* (subpath ' + json.dumps(str(work / 'grade-repo')) + '))\n'
    path = base / 'control' / (run_id + '-grade-revised.sb')
    with path.open('x') as stream:
        stream.write(text)
    return path


def environment(work, policy_path):
    env = {k: v for k, v in os.environ.items() if k not in ('PYTHONPATH', 'PYTHONHOME')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    env['AMIND_APP_COMMAND_PREFIX_JSON'] = json.dumps(['/usr/bin/sandbox-exec', '-f', str(policy_path)])
    env['AMIND_GRADER_SCRATCH'] = str(work / 'grade-revised-scratch')
    return env


def preflight(work, repo, policy_path):
    paths = {'own_revised_repo': repo / 'README.md',
             'original_repo': work / 'repo/README.md',
             'original_grade_repo': work / 'grade-repo/README.md',
             'skills': work / 'skills/eval-improve/SKILL.md',
             'output': work / 'output/final.txt',
             'private_grader': HERE / 'grade_release.py'}
    # Missing protected files are recorded, rather than mistaken for proof of denial.
    paths = {k: str(v) for k, v in paths.items() if v.is_file()}
    assert 'own_revised_repo' in paths and 'private_grader' in paths
    program = 'PATHS=' + repr(paths) + '\n' + '''import errno,json,pathlib,socket
result={}
for key,path in PATHS.items():
 try:pathlib.Path(path).read_bytes();result[key]='ALLOWED'
 except OSError as exc:result[key]='DENIED' if exc.errno in (errno.EPERM,errno.EACCES) else 'OTHER_ERROR'
try:
 sock=socket.socket();sock.bind(('127.0.0.1',0));sock.close();result['network_bind']='ALLOWED'
except OSError as exc:result['network_bind']='DENIED' if exc.errno in (errno.EPERM,errno.EACCES) else 'OTHER_ERROR'
print(json.dumps(result))
'''
    p = subprocess.run(['/usr/bin/sandbox-exec', '-f', str(policy_path), 'python3', '-B', '-c', program],
                       cwd=repo, capture_output=True, text=True, timeout=8)
    assert p.returncode == 0, p.stderr
    result = json.loads(p.stdout)
    assert result['own_revised_repo'] == 'ALLOWED', result
    assert all(v == 'DENIED' for k, v in result.items() if k != 'own_revised_repo'), result
    return {'checks': result, 'policy': str(policy_path), 'policy_sha256': sha(policy_path),
            'same_frozen_policy_plus_original_grade_repo_denial': True}


def grade(task_id, repo, env, destination):
    name = {'V-RELEASE': 'grade_release.py', 'V-CALIBRATE': 'grade_calibrate.py'}[task_id]
    command = ['python3', '-B', str(HERE / name), '--repo', str(repo)]
    p = subprocess.run(command, cwd=repo.parent, env=env, capture_output=True, text=True, timeout=180)
    destination.mkdir(parents=True)
    (destination / 'stdout.txt').write_text(p.stdout)
    (destination / 'stderr.txt').write_text(p.stderr)
    assert p.returncode == 0, (task_id, p.stderr)
    result = json.loads(p.stdout)
    assert result['task_id'] == task_id and result['max_score'] == 5
    write(destination / 'grade.json', result)
    return result

#!/usr/bin/env python3
"""One-shot semantic grade of repaired Durable deliveries after all six capture.

Preparation alone does not inspect partial target outputs. At execution, the
full repair-plan capture-existence gate precedes every capture/repo read.
"""
import datetime
import importlib.util
import json
import shutil
from pathlib import Path

from rescore import HERE, OUT, ROOT, IGNORE, grade, inventory, read, sha, write


def portable_policy_text(runner, base, run_id):
    """Same rule generation as the frozen runner, without replacing its policy."""
    work = base / run_id
    text = '(version 1)\n(allow default)\n'
    for path in runner.protected_paths(base, run_id):
        text += '(deny file-read* file-write* (subpath ' + json.dumps(path) + '))\n'
    for path in (work / 'skills', work / 'task.json', work / 'repo/tests'):
        text += '(deny file-write* (subpath ' + json.dumps(str(path)) + '))\n'
    text += ('(deny file-write* (literal "/Users/damonalbarn/.codex/config.toml") '
             '(literal "/Users/damonalbarn/.codex/auth.json"))\n')
    text += '(deny network*)\n'
    for path in (work / 'skills', work / 'repo', work / 'output'):
        text += '(deny file-read* file-write* (subpath ' + json.dumps(str(path)) + '))\n'
    return text


def main():
    plan_path = OUT / 'repair-plan.json'
    plan = read(plan_path)
    assert len(plan['runs']) == 6, 'repair-plan must contain the full six-run phase'
    capture_paths = [OUT / 'runs' / run['run_id'] / 'capture.json' for run in plan['runs']]
    missing = [str(path) for path in capture_paths if not path.is_file()]
    if missing:
        raise RuntimeError('Full-phase gate closed: missing ' + ', '.join(missing))
    # Do not read even the Engineering capture content above this point.
    runs = [run for run in plan['runs'] if run['axis'] == 'engineering']
    assert {run['run_id'] for run in runs} == {'W043', 'W044', 'W045'}
    assert {run['task_id'] for run in runs} == {'E-DURABLE'}
    assert {run['arm'] for run in runs} == {'repaired'}
    assert sorted(run['rep'] for run in runs) == [0, 1, 2]
    for run in runs:
        capture = read(OUT / 'runs' / run['run_id'] / 'capture.json')
        assert capture['status'] == 'captured', (run['run_id'], capture['status'])

    manifest = read(HERE / 'revision-manifest.json')
    # Reuse the exact grader/common/wrapper bytes calibrated for the main phase.
    grader_hashes = {name: sha(HERE / name) for name in
                     ('grade_durable.py', 'grade_common.py', 'rescore.py')}
    assert all(digest == manifest['files_sha256'][name]
               for name, digest in grader_hashes.items())
    comparison_path = OUT / 'main-plan-engineering-scores-revised.json'
    comparison = read(comparison_path)
    current_ids = {'W003', 'W026', 'W031'}
    history = [row for row in comparison['rows'] if row['run_id'] in current_ids]
    assert {row['run_id'] for row in history} == current_ids
    assert all(row['task_id'] == 'E-DURABLE' and row['arm'] == 'current'
               and row['score'] == row['max_score'] == 6 for row in history)

    destination = OUT / 'app-grades-repaired-revised'
    result_path = OUT / 'repair-plan-engineering-scores-revised.json'
    assert not destination.exists() and not result_path.exists(), 'refuse to replace revised evidence'
    immutable = {str(plan_path): sha(plan_path), str(comparison_path): sha(comparison_path)}
    for name, digest in grader_hashes.items():
        immutable[str(HERE / name)] = digest
    for run in runs:
        folder = OUT / 'runs' / run['run_id']
        immutable.update({str(folder / name): digest for name, digest in inventory(folder).items()})
        original_grade = OUT / 'app-grades' / run['run_id']
        if original_grade.is_dir():
            immutable.update({str(original_grade / name): digest
                              for name, digest in inventory(original_grade).items()})
    frozen = read(OUT / 'measurement-files.json')
    assert all(sha(ROOT / path) == digest for path, digest in frozen.items())
    destination.mkdir()
    write(destination / 'original-evidence-before.json', immutable)
    spec = importlib.util.spec_from_file_location('workplace_runner', ROOT / 'scripts/run_amind_workplace_trials.py')
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    base = Path(plan['root'])
    rows = []
    for run in sorted(runs, key=lambda value: value['rep']):
        run_id = run['run_id']
        workspace = Path(run['workspace'])
        repo = workspace / 'grade-repaired-revised-repo'
        assert not repo.exists(), ('refuse to reuse revised portable repo', run_id)
        shutil.copytree(OUT / 'runs' / run_id / 'repo', repo, ignore=IGNORE)
        policy = base / 'control' / (run_id + '-grade-repaired-revised.sb')
        assert not policy.exists()
        expected_policy = portable_policy_text(runner, base, run_id)
        original_policy = base / 'control' / (run_id + '-grade.sb')
        if original_policy.exists():
            assert original_policy.read_text() == expected_policy
            policy.write_bytes(original_policy.read_bytes())
            policy_provenance = 'byte-identical copy of original frozen-grader policy'
        else:
            policy.write_text(expected_policy)
            policy_provenance = 'same frozen protected_paths and grading rules; original policy not yet present'
        result = grade('E-DURABLE', repo, workspace / 'grade-repaired-revised-scratch',
                       policy, destination / run_id)
        row = {key: run[key] for key in ('run_id', 'task_id', 'rep', 'arm')}
        row.update(grade_status='graded', score=result['score'], max_score=result['max_score'],
                   probe_passed=result['probe_passed'], probe_total=result['probe_total'],
                   guardrails_passed=result['fatal_pass'],
                   failed_probes=[case['id'] for case in result['cases'] if not case['passed']],
                   portable_no_skill_dependency=True, network_denied_during_probes=True,
                   policy_provenance=policy_provenance,
                   original_frozen_grade_path=str(OUT / 'app-grades' / run_id / 'grade.json'))
        write(destination / run_id / 'summary.json', row)
        rows.append(row)
        print(json.dumps(row), flush=True)
    assert all(sha(ROOT / path) == digest for path, digest in frozen.items())
    assert all(sha(Path(path)) == digest for path, digest in immutable.items())
    result = {
        'created_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'rows': rows, 'independent_tasks': 1, 'repetitions_per_task_arm': 3,
        'phase': 'post-repair reused-task verification; not a new holdout',
        'full_six_capture_existence_gate_passed': True,
        'gate_capture_paths': [str(path) for path in capture_paths],
        'same_main_revised_grader_files_sha256': grader_hashes,
        'historical_comparison': {
            'source': str(comparison_path), 'source_sha256': sha(comparison_path),
            'rows': history, 'interpretation': 'Historical main current was6/6 for all3; no new causal or independent-task comparison.'},
        'original_measurement_files_unchanged': len(frozen),
        'original_capture_grade_files_unchanged': len(immutable),
        'target_model_calls': 0,
        'limits': ['Same single Durable task reused after diagnostics; not a new holdout.',
                   'Three repetitions and fourteen probes do not add independent task families.',
                   'Original frozen grades and captures are never replaced.']}
    write(result_path, result)
    write(destination / 'original-evidence-after.json', {
        'all_original_evidence_unchanged': True, 'original_evidence_file_count': len(immutable),
        'frozen_measurement_files_unchanged': len(frozen)})


if __name__ == '__main__':
    main()

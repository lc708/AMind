#!/usr/bin/env python3
"""Apply disclosed semantic grader corrections to all captured Eval deliveries."""
import argparse
import importlib.util
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('revised_eval_lane', HERE / 'revised-private/lane.py')
lane = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lane)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='main-plan.json')
    args = parser.parse_args()
    assert Path(args.plan).name == args.plan and args.plan.endswith('.json')
    plan_path = lane.OUT / args.plan
    plan = lane.read(plan_path)
    runs = [r for r in plan['runs'] if r['task_id'] in ('V-RELEASE', 'V-CALIBRATE')]
    assert runs
    output = lane.OUT / (Path(args.plan).stem + '-evaluation-scores-revised.json')
    assert not output.exists(), 'do not replace revised scores'
    calibration = lane.read(lane.HERE / 'calibration/summary.json')
    assert calibration['passed'], 'calibration must pass before captured deliveries'
    frozen = lane.read(lane.HERE / 'revision-freeze.json')
    for path, digest in frozen['files'].items():
        assert lane.sha(lane.ROOT / path) == digest, path
    provenance = lane.read(lane.HERE / 'original-sources.json')
    for path, row in provenance['original_sources'].items():
        assert lane.sha(lane.ROOT / path) == row['sha256'], path
    for run in runs:
        assert (lane.OUT / 'runs' / run['run_id'] / 'capture.json').is_file()
        assert not (lane.OUT / 'app-grades-revised' / run['run_id']).exists()
        assert not (Path(run['workspace']) / 'grade-revised-repo').exists()
    frozen_runner = lane.runner(plan)
    before = {}
    for run in runs:
        for folder in (lane.OUT / 'runs' / run['run_id'], lane.OUT / 'app-grades' / run['run_id']):
            before[str(folder.relative_to(lane.ROOT))] = lane.inventory(folder)
    rows = []
    for run in runs:
        rid = run['run_id']
        work = Path(run['workspace'])
        captured = lane.read(lane.OUT / 'runs' / rid / 'capture.json')
        assert captured['status'] == 'captured', (rid, captured['status'])
        source = lane.OUT / 'runs' / rid / 'repo'
        repo = work / 'grade-revised-repo'
        shutil.copytree(source, repo, ignore=frozen_runner.IGNORE)
        assert lane.inventory(source) == lane.inventory(repo)
        policy = lane.policy(Path(plan['root']), rid, frozen_runner)
        checks = lane.preflight(work, repo, policy)
        destination = lane.OUT / 'app-grades-revised' / rid
        result = lane.grade(run['task_id'], repo, lane.environment(work, policy), destination)
        lane.write(destination / 'isolation.json', checks)
        original_path = lane.OUT / 'app-grades' / rid / 'grade.json'
        original = lane.read(original_path)
        changed = [{'case_id': new['id'], 'old_pass': old['pass'], 'revised_pass': new['pass']}
                   for old, new in zip(original['cases'], result['cases']) if old['pass'] != new['pass']]
        row = {key: run[key] for key in ('run_id', 'task_id', 'rep', 'arm')}
        row.update(runtime_status='captured', grade_status='graded', score=result['score'],
                   max_score=5, guardrails_passed=result['guardrails_passed'],
                   probe_passed=result['probe_passed'], probe_total=result['probe_total'],
                   original_score=original['score'], original_guardrails_passed=original['guardrails_passed'],
                   original_grade_sha256=lane.sha(original_path), changed_cases=changed,
                   portable_no_skill_dependency=True, network_denied_during_probes=True)
        lane.write(destination / 'summary.json', row)
        rows.append(row)
        print(__import__('json').dumps(row), flush=True)
    for folder, digest in before.items():
        assert lane.inventory(lane.ROOT / folder) == digest, 'original modified: ' + folder
    for path, row in provenance['original_sources'].items():
        assert lane.sha(lane.ROOT / path) == row['sha256'], path
    cells = {}
    for run in runs:
        cells.setdefault(run['task_id'], {}).setdefault(run['arm'], 0)
        cells[run['task_id']][run['arm']] += 1
    lane.write(output, {'rows': rows, 'independent_tasks': len(cells),
                        'planned_runs_per_task_arm': cells,
                        'revision': 'Post-outcome measurement-contract correction, applied symmetrically; no product/model changes and no new holdout claim.',
                        'calibration_summary_sha256': lane.sha(lane.HERE / 'calibration/summary.json'),
                        'revision_freeze_sha256': lane.sha(lane.HERE / 'revision-freeze.json'),
                        'original_artifacts_unchanged': True,
                        'original_artifact_inventories': before,
                        'note': 'Original Eval/engineering application scores remain intact; this file contains only the two Eval tasks.'})


if __name__ == '__main__':
    main()

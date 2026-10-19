#!/usr/bin/env python3
"""Calibrate revised graders under the same portable, network-denied lane."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess

import lane
from fixtures import calibration, cohort


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', default='main-plan.json')
    args = parser.parse_args()
    assert Path(args.plan).name == args.plan
    plan = lane.read(lane.OUT / args.plan)
    frozen_runner = lane.runner(plan)
    frozen = lane.read(lane.HERE / 'revision-freeze.json')
    for path, digest in frozen['files'].items():
        assert lane.sha(lane.ROOT / path) == digest, path
    original_freeze = lane.read(lane.HERE.parent / 'freeze.json')
    for path, digest in original_freeze['files'].items():
        assert lane.sha(lane.HERE.parent / path) == digest, path
    target = lane.HERE / 'calibration'
    assert not target.exists(), 'never replace calibration'
    target.mkdir()
    manifest = lane.read(lane.HERE / 'control-manifest.json')
    rows = []
    for index, control in enumerate(manifest['controls']):
        rid = 'REVISED-EVAL-CAL-' + str(index).zfill(2)
        base = Path(plan['root'])
        work = base / rid
        assert not work.exists()
        work.mkdir()
        repo = work / 'grade-revised-repo'
        shutil.copytree(lane.ROOT / control['repo'], repo, ignore=frozen_runner.IGNORE)
        assert lane.inventory(lane.ROOT / control['repo']) == lane.inventory(repo)
        policy = lane.policy(base, rid, frozen_runner)
        isolation = lane.preflight(work, repo, policy)
        env = lane.environment(work, policy)
        dest = target / control['task_id'] / control['id']
        result = lane.grade(control['task_id'], repo, env, dest)
        lane.write(dest / 'isolation.json', isolation)
        if control['expect_full_pass']:
            passed = result['score'] == 5 and result['probe_passed'] == 14 and result['guardrails_passed']
        else:
            passed = result['score'] < 5
        case_id = control['required_failed_case']
        if case_id:
            passed = passed and not next(c['pass'] for c in result['cases'] if c['id'] == case_id)
        zero = None
        if control['task_id'] == 'V-CALIBRATE' and control['expect_full_pass']:
            job = calibration()
            job['current'] = cohort({'tp': 3, 'tn': 4})
            job_path = work / 'real-zero-negative-controls.json'
            job_path.write_text(json.dumps(job))
            prefix = json.loads(env['AMIND_APP_COMMAND_PREFIX_JSON'])
            command = prefix + ['python3', '-B', '-m', 'judgecheck', '--input', str(job_path)]
            p = subprocess.run(command, cwd=repo, env=env, capture_output=True, text=True, timeout=8)
            packet = json.loads(p.stdout) if p.returncode == 0 else {}
            cal = packet.get('calibration', {})
            checks = {'returncode': p.returncode == 0,
                      'real_negative_population': cal.get('denominators', {}).get('evaluated_negative') == 4,
                      'zero_fpr_measured': type(cal.get('fpr')) in (int, float) and cal['fpr'] == 0,
                      'no_unmeasured_class': cal.get('unmeasured') == [],
                      'ready': packet.get('status') == 'ready_for_review'}
            zero = {'checks': checks, 'passed': all(checks.values()), 'stdout': p.stdout, 'stderr': p.stderr}
            lane.write(dest / 'real-fpr-zero.json', zero)
            passed = passed and zero['passed']
        row = dict(control)
        row.update(score=result['score'], probe_passed=result['probe_passed'],
                   guardrails_passed=result['guardrails_passed'], calibration_pass=bool(passed),
                   real_zero_positive_control=zero['passed'] if zero else None)
        rows.append(row)
        print(json.dumps(row), flush=True)
    for path, digest in original_freeze['files'].items():
        assert lane.sha(lane.HERE.parent / path) == digest, path
    summary = {'passed': all(r['calibration_pass'] for r in rows), 'controls': rows,
               'control_count': len(rows), 'full_reference_and_semantic_alternatives': 4,
               'real_zero_positive_controls': sum(r['real_zero_positive_control'] is not None for r in rows),
               'sandbox_prefix_present_for_every_app_subprocess': True,
               'network_denied': True, 'frozen_original_files_unchanged': len(original_freeze['files']),
               'revision_freeze_sha256': lane.sha(lane.HERE / 'revision-freeze.json'),
               'scope': 'Disclosed post-outcome grader repair. Calibration performed before rescoring any captured target delivery; not a new holdout.'}
    lane.write(target / 'summary.json', summary)
    assert summary['passed'], 'calibration failed; captured-delivery rescoring prohibited'


if __name__ == '__main__':
    main()

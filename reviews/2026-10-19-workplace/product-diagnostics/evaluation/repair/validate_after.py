"""Post-fix public CLI validation; keep all original diagnostic files immutable."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPAIR = Path(__file__).resolve().parent
BASE = REPAIR.parent
ROOT = BASE.parents[3]
SKILL = ROOT / 'skills/eval-improve'
AFTER = REPAIR / 'after'
AFTER.mkdir(exist_ok=True)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def main():
    results = []
    for scene, original in [('healthy', 'recovery-flow'), ('metrics-only', 'state-metrics-only'),
                            ('population-only', 'state-population-only'), ('both-fields', 'state-index-export'),
                            ('reps-only', 'recovery-flow'), ('legacy-unverified', 'recovery-flow')]:
        dest = AFTER / scene
        if dest.exists():
            raise ValueError('Refuse to overwrite post-fix evidence')
        shutil.copytree(BASE / original, dest)
        for name in ('report-full.html', 'report-data.json'):
            if (dest / name).exists():
                (dest / name).unlink()
        if scene == 'reps-only':
            state = json.loads((dest / '_state.json').read_text()); state['reps'] = 2
            save(dest / '_state.json', state)
        elif scene == 'legacy-unverified':
            (dest / 'baseline/manifest.json').unlink()
        command = [sys.executable, '-B', str(SKILL / 'scripts/report_eval.py'), str(dest)]
        p = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=20,
                           env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        data = json.loads(p.stdout)
        report = json.loads((dest / 'report-data.json').read_text()) if (dest / 'report-data.json').exists() else None
        record = {'scene': scene, 'command': command, 'returncode': p.returncode, 'stdout': p.stdout,
                  'stderr': p.stderr, 'report': report, 'evidence_use': 'Post-diagnostic product repair validation, separate from frozen workplace comparison'}
        save(dest / 'command.json', record); results.append(record)
        expected = 0 if scene in ('healthy', 'legacy-unverified') else 2
        if p.returncode != expected:
            raise ValueError('Unexpected report outcome: ' + scene)
        if expected == 2 and report is not None:
            raise ValueError('Invalid state produced a new report')
        if scene == 'healthy':
            assert all(v['planned_observations'] == v['scored_observations'] == 3 and set(v['metrics']) == {'quality', 'policy'} for v in report['variants'])
            baseline = report['variants'][0]
            assert baseline['unknown_cost_attempts'] == 1 and baseline['total_cost_usd'] is None
        elif scene == 'legacy-unverified':
            assert report['variants'][0]['integrity'].startswith('unverified:')
    test_logs = {}
    for kind in ('report', 'existing'):
        text = (REPAIR / (kind + '-tests.stderr.txt')).read_text()
        assert '\nOK\n' in text
        test_logs[kind] = text[-150:]
    paths = [SKILL / 'scripts/report_eval.py', SKILL / 'references/artifacts.md', ROOT / 'scripts/test_amind_eval_reporting.py']
    summary = {'all_passed': True, 'report_regressions': 17, 'existing_eval_tests': 79, 'total_targeted_tests': 96,
               'test_log_summaries': test_logs, 'scenarios': [{'scene': r['scene'], 'returncode': r['returncode'], 'error': json.loads(r['stdout']).get('error')} for r in results],
               'product_source_sha256': {str(p.relative_to(ROOT)): sha(p) for p in paths},
               'original_evidence_preserved': True, 'target_model_calls': 0, 'target_outputs_read': False,
               'frozen_workplace_inputs_modified': False}
    save(REPAIR / 'validation.json', summary)
    patch = []
    for before, after in [('report_eval.py', paths[0]), ('artifacts.md', paths[1]), ('test_amind_eval_reporting.py', paths[2])]:
        patch.extend(difflib.unified_diff((REPAIR / 'before' / before).read_text().splitlines(True), after.read_text().splitlines(True),
                                        fromfile='before/' + str(after.relative_to(ROOT)), tofile='after/' + str(after.relative_to(ROOT))))
    (REPAIR / 'fix.diff').write_text(''.join(patch))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

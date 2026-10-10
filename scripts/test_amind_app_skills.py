import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'skills/eval-improve'
sys.path.insert(0, str(SKILL / 'scripts'))
import kernel_common
spec = importlib.util.spec_from_file_location('compare_runs', SKILL / 'scripts/compare_runs.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)

install_spec = importlib.util.spec_from_file_location('installer', ROOT / 'scripts/install_amind_series.py')
installer = importlib.util.module_from_spec(install_spec)
install_spec.loader.exec_module(installer)


class EvalImproveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='eval-improve-offline-')
        self.root = Path(self.temp.name)
        self.state = {'metrics': [{'id': 'quality', 'label': 'Quality', 'kind': 'binary'}],
                      'train_ids': [], 'val_ids': ['a', 'b', 'c', 'd'], 'test_ids': [],
                      'synthetic': True}
        self.write_state()
        self.rows = {}
        for variant, scores in [('baseline', [0, 0, 1, 0]), ('v1', [1, 1, 1, 1])]:
            self.rows[variant] = [
                {'prompt_id': case, 'rep': rep, 'prompt': '<script>alert("synthetic")</script>',
                 'status': 'ok', 'grade': {'quality': score}, 'model': 'mock-model',
                 'meta': {'synthetic': True}}
                for case, score in zip(self.state['val_ids'], scores)
                for rep in range(2)]
            self.write_rows(variant)

    def tearDown(self):
        self.temp.cleanup()

    def write_state(self):
        (self.root / '_state.json').write_text(json.dumps(self.state))
        for variant in ('baseline','v1'):
            if (self.root / variant / 'results.jsonl').exists(): self.write_manifest(variant)

    def write_manifest(self, variant):
        identity = {'split':'val','reps':2,'metrics':self.state['metrics'],
                    'splits':{k:self.state.get(k+'_ids',[]) for k in ('train','val','test')},
                    'case_groups':{key:key for key in self.state['val_ids']}}
        path = self.root / variant
        manifest = {'schema_version':2,'comparison_identity':identity,
                    'comparison_hash':kernel_common.sha(identity),'status':'complete',
                    'results_sha256':kernel_common.sha((path/'results.jsonl').read_bytes())}
        (path/'manifest.json').write_text(json.dumps(manifest))

    def write_rows(self, variant):
        path = self.root / variant
        (path / 'traces').mkdir(parents=True, exist_ok=True)
        (path / 'results.jsonl').write_text(''.join(json.dumps(r) + '\n' for r in self.rows[variant]))
        self.write_manifest(variant)
        for r in self.rows[variant]:
            (path / 'traces' / f"{r['prompt_id']}_rep{r['rep']}.json").write_text(
                json.dumps([{'role': 'user', 'content': 'Synthetic fixture only'}]))

    def compare(self, **kwargs):
        return comparison.compare(self.root, 'v1', 'val', 'quality', 2, samples=1000, **kwargs)

    def test_paired_means_and_repeatability(self):
        result = self.compare()
        self.assertEqual(result, self.compare())
        self.assertEqual(result['complete_pairs'], 4)
        self.assertEqual(result['baseline_mean'], .25)
        self.assertEqual(result['candidate_mean'], 1)
        self.assertEqual(result['improvement'], .75)
        self.assertEqual(result['verdict'], 'improvement_clears_threshold')
        self.assertEqual(self.compare(minimum=1)['verdict'], 'inconclusive')

    def test_average_repetitions_before_pairing(self):
        self.rows['v1'][0]['grade']['quality'] = 0
        self.write_rows('v1')
        self.assertEqual(self.compare()['candidate_mean'], .875)

    def test_lower_is_better(self):
        self.state['metrics'][0]['better']='lower'
        self.write_state()
        result = self.compare(direction='lower')
        self.assertEqual(result['improvement'], -.75)
        self.assertEqual(result['verdict'], 'regression')

    def test_missing_case_does_not_make_aggregate_look_better(self):
        self.rows['v1'] = [r for r in self.rows['v1'] if r['prompt_id'] != 'a']
        self.write_rows('v1')
        result = self.compare()
        self.assertEqual(result['verdict'], 'incomplete')
        self.assertNotIn('candidate_mean', result)
        call = subprocess.run(['python3', str(SKILL / 'scripts/compare_runs.py'),
                               '--flow', str(self.root), '--candidate', 'v1',
                               '--split', 'val', '--metric', 'quality', '--reps', '2'],
                              text=True, capture_output=True)
        self.assertEqual(call.returncode, 2)
        self.assertEqual(json.loads(call.stdout)['verdict'], 'incomplete')

    def test_duplicate_attempt_is_rejected(self):
        self.rows['v1'].append(self.rows['v1'][0].copy())
        self.write_rows('v1')
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.compare()

    def test_unscored_and_extra_repetitions_are_incomplete(self):
        for problem in ['truncated', 'nonfinite', 'extra']:
            with self.subTest(problem=problem):
                old = json.loads(json.dumps(self.rows['v1']))
                if problem == 'truncated':self.rows['v1'][0]['status'] = 'truncated'
                elif problem == 'nonfinite':self.rows['v1'][0]['grade']['quality'] = float('nan')
                else:self.rows['v1'].append({**self.rows['v1'][0], 'rep': 2})
                self.write_rows('v1')
                self.assertEqual(self.compare()['verdict'], 'incomplete')
                self.rows['v1'] = old
        self.write_rows('v1')

    def test_split_overlap_is_rejected(self):
        self.state['test_ids'] = ['a']
        self.write_state()
        with self.assertRaisesRegex(ValueError, 'overlap'):
            self.compare()

    def test_one_case_cannot_claim_confidence(self):
        self.state['val_ids'] = ['a']
        self.write_state()
        for variant in ('baseline','v1'):
            self.rows[variant]=[r for r in self.rows[variant] if r['prompt_id']=='a']
            self.write_rows(variant)
        self.assertEqual(self.compare()['verdict'], 'insufficient_independent_cases')

    def test_report_values_escaping_and_idempotence(self):
        command = ['node', str(SKILL / 'scripts/build-report.mjs'), str(self.root)]
        first = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        report = (self.root / 'report.html').read_text()
        self.assertIn('&lt;script&gt;', report)
        self.assertNotIn('<script>alert(', report)
        self.assertIn('baseline/traces/a_rep0.json', report)
        tsv = (self.root / 'trajectory/scores.tsv').read_text()
        values = {row.split('\t')[0]: row.split('\t')[1:]
                  for row in tsv.strip().splitlines()[1:]}
        self.assertEqual(values['a'][0], 'val')
        self.assertEqual([float(x) for x in values['a'][1:]], [0.0, 1.0])
        second = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(tsv, (self.root / 'trajectory/scores.tsv').read_text())


class CodexCollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='amind-collector-synthetic-')
        self.root = Path(self.temp.name)
        self.workspace = self.root / 'target with spaces'
        self.workspace.mkdir()
        self.flow = self.root / 'flow'
        self.flow.mkdir()
        self.cases = [{'id': 'a', 'prompt': 'Synthetic input A; literal $(no-execution)'},
                      {'id': 'b', 'prompt': 'Synthetic input B'}]
        self.state = {'train_ids': [], 'val_ids': ['a', 'b'], 'test_ids': [], 'reps': 2,
                      'metrics': [{'id': 'quality', 'kind': 'binary'}]}
        self.inputs = self.root / 'inputs.jsonl'
        self.save()
        self.fake = self.root / 'fake-codex'
        self.fake.write_text('#!' + sys.executable + '\n' + r'''
import json, sys, time
from pathlib import Path
if sys.argv[1:] == ['--version']:
    print('synthetic-codex 0.0.0')
    sys.exit(0)
args = sys.argv[1:]
prompt = sys.stdin.read()
workspace = Path(args[args.index('--cd') + 1])
with (workspace / 'invocations.jsonl').open('a') as log:
    log.write(json.dumps({'args': args, 'prompt': prompt}) + '\n')
if prompt == 'HANG':
    time.sleep(30)
if prompt == 'FAIL':
    print(json.dumps({'type': 'turn.failed', 'error': {'message': 'synthetic failure'}}))
    sys.exit(1)
if prompt != 'NOFINAL':
    Path(args[args.index('--output-last-message') + 1]).write_text('Synthetic output: ' + prompt)
if prompt == 'BAD':
    print('not a JSON event')
elif prompt != 'NODONE':
    event = {'type': 'turn.completed'}
    if prompt != 'NOUSAGE':
        event['usage'] = {'input_tokens': 12, 'cached_input_tokens': 8, 'output_tokens': 3}
    print(json.dumps(event))
''')
        self.fake.chmod(0o755)

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.flow / '_state.json').write_text(json.dumps(self.state))
        self.inputs.write_text(''.join(json.dumps(case) + '\n' for case in self.cases))

    def test_casefold_id_collision_rejected_before_collection(self):
        self.cases[0]['id']='A'; self.cases[1]['id']='a'
        self.state['val_ids']=['A','a']; self.save()
        code,result=self.run_collector()
        self.assertEqual(code,2)
        self.assertIn('collision',json.dumps(result))
        self.assertFalse((self.workspace/'invocations.jsonl').exists())

    def run_collector(self, *extra):
        command = [sys.executable, '-B', str(SKILL / 'scripts/collect_codex.py'),
                   '--flow', str(self.flow), '--cases', str(self.inputs),
                   '--workspace', str(self.workspace), '--variant', 'baseline',
                   '--split', 'val', '--reps', '2', '--target-version', 'synthetic-fixture-v1',
                   '--codex', str(self.fake)] + list(extra)
        call = subprocess.run(command, text=True, capture_output=True, timeout=15)
        return call.returncode, json.loads(call.stdout)

    def rows(self):
        return [json.loads(line) for line in (self.flow / 'baseline/captures.jsonl').read_text().splitlines()]

    def test_plan_never_launches_codex_or_creates_variant(self):
        code, result = self.run_collector('--codex', '/nonexistent-codex')
        self.assertEqual(code, 0)
        self.assertEqual(result['planned_runs'], 4)
        self.assertFalse((self.flow / 'baseline').exists())
        self.assertFalse((self.workspace / 'invocations.jsonl').exists())

    def test_execution_preserves_native_usage_and_leaves_outputs_ungraded(self):
        code, result = self.run_collector('--execute', '--model', 'user-selected-fixture', '--profile', 'fixture')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['ungraded'], 4)
        self.assertTrue(result['complete'])
        rows = self.rows()
        self.assertEqual({(r['prompt_id'], r['rep']) for r in rows}, {('a', 0), ('a', 1), ('b', 0), ('b', 1)})
        for row in rows:
            self.assertEqual(row['status'], 'ungraded')
            self.assertEqual(row['grade'], {})
            self.assertNotIn('model', row)
            self.assertNotIn('cost', row)
            self.assertEqual(row['meta']['provider_native_usage'][0]['cached_input_tokens'], 8)
        self.assertFalse((self.flow / 'baseline/results.jsonl').exists())
        invocations = [json.loads(x) for x in (self.workspace / 'invocations.jsonl').read_text().splitlines()]
        for call in invocations:
            self.assertEqual(call['args'][call['args'].index('--sandbox') + 1], 'read-only')
            self.assertIn('--ephemeral', call['args'])
            self.assertEqual(call['args'][-1], '-')
            self.assertIn('user-selected-fixture', call['args'])
        self.assertEqual(invocations[0]['prompt'], self.cases[0]['prompt'])
        manifest = json.loads((self.flow / 'baseline/run-plan.json').read_text())
        self.assertEqual(manifest['codex_version'], 'synthetic-codex 0.0.0')
        self.assertEqual(manifest['cases_sha256'], hashlib.sha256(self.inputs.read_bytes()).hexdigest())

    def test_budget_answer_fields_and_overlap_block_before_execution(self):
        code, result = self.run_collector('--execute', '--max-runs', '3')
        self.assertEqual(code, 2)
        self.assertIn('exceed', result['error'])
        self.cases[0]['expected'] = 'private gold'
        self.save()
        self.assertEqual(self.run_collector('--execute')[0], 2)
        del self.cases[0]['expected']
        self.state['test_ids'] = ['a']
        self.save()
        self.assertEqual(self.run_collector('--execute')[0], 2)
        self.assertFalse((self.workspace / 'invocations.jsonl').exists())

    def test_partial_failures_are_retained_and_counted_without_retries(self):
        self.cases[0]['prompt'] = 'FAIL'
        self.save()
        code, result = self.run_collector('--execute')
        self.assertEqual(code, 2)
        self.assertEqual(result['attempted_runs'], 4)
        self.assertEqual(result['failed'], 2)
        self.assertEqual(result['ungraded'], 2)
        errors = (self.flow / 'baseline/errors.jsonl').read_text().splitlines()
        self.assertEqual(len(errors), 2)
        self.assertEqual(json.loads(errors[0])['status'], 'runtime_error')
        self.assertEqual(len(self.rows()), 4)

    def single_case(self, prompt):
        self.cases = [{'id': 'a', 'prompt': prompt}]
        self.state['val_ids'] = ['a']
        self.state['reps'] = 1
        self.save()

    def test_timeout_is_an_explicit_failed_attempt(self):
        self.single_case('HANG')
        code, result = self.run_collector('--execute', '--reps', '1', '--timeout', '1')
        self.assertEqual(code, 2)
        self.assertEqual(result['failed'], 1)
        self.assertEqual(self.rows()[0]['status'], 'timeout')

    def test_malformed_or_missing_completion_is_not_success(self):
        for prompt in ['BAD', 'NODONE', 'NOFINAL']:
            with self.subTest(prompt=prompt):
                self.single_case(prompt)
                code, result = self.run_collector('--execute', '--reps', '1', '--variant', 'v' + str(len(prompt)))
                self.assertEqual(code, 2, result)
                row = json.loads((self.flow / ('v' + str(len(prompt))) / 'captures.jsonl').read_text())
                self.assertEqual(row['status'], 'incomplete')

    def test_missing_usage_is_not_fabricated(self):
        self.single_case('NOUSAGE')
        self.assertEqual(self.run_collector('--execute', '--reps', '1')[0], 0)
        row = self.rows()[0]
        self.assertEqual(row['meta']['provider_native_usage'], [])
        self.assertNotIn('usage', row)

    def test_existing_variant_is_preserved(self):
        self.assertEqual(self.run_collector('--execute')[0], 0)
        before = (self.flow / 'baseline/captures.jsonl').read_bytes()
        self.assertEqual(self.run_collector('--execute')[0], 2)
        self.assertEqual(before, (self.flow / 'baseline/captures.jsonl').read_bytes())


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='amind-install-offline-')
        self.root = Path(self.temp.name)
        self.destination = self.root / 'skills'

    def tearDown(self):
        self.temp.cleanup()

    def test_preview_install_and_unchanged_reinstall(self):
        self.assertEqual(installer.install(self.destination)['mode'], 'plan')
        self.assertFalse(self.destination.exists())
        result = installer.install(self.destination, apply=True)
        self.assertTrue(result['verified'])
        for name in installer.PACKAGES:
            self.assertEqual(installer.inventory(self.destination / name), installer.inventory(installer.SOURCE / name))
        second = installer.install(self.destination, apply=True)
        self.assertTrue(all(item['action'] == 'unchanged' for item in second['skills']))

    def test_replacement_preserves_custom_copy_outside_discovery(self):
        old = self.destination / 'eval-improve'
        old.mkdir(parents=True)
        (old / 'SKILL.md').write_text('custom local instructions')
        with self.assertRaisesRegex(ValueError, '--replace'):
            installer.install(self.destination, apply=True)
        self.assertFalse((self.destination / 'amind-engineering').exists())
        result = installer.install(self.destination, apply=True, replace=True)
        backup = Path(result['backup'])
        self.assertEqual((backup / 'eval-improve/SKILL.md').read_text(), 'custom local instructions')
        self.assertNotIn(self.destination, backup.parents)

    def test_interrupted_second_install_rolls_back_first(self):
        installer.install(self.destination, apply=True)
        for name in installer.PACKAGES:
            (self.destination / name / 'SKILL.md').write_text('local ' + name)
        original_rename = Path.rename

        def fail_stage(path, target):
            if path.name == 'eval-improve' and path.parent.name.startswith('.amind-stage-'):
                raise OSError('synthetic disk failure')
            return original_rename(path, target)

        with mock.patch.object(Path, 'rename', fail_stage):
            with self.assertRaisesRegex(OSError, 'synthetic disk'):
                installer.install(self.destination, apply=True, replace=True)
        for name in installer.PACKAGES:
            self.assertEqual((self.destination / name / 'SKILL.md').read_text(), 'local ' + name)

    def test_symlink_destination_is_refused(self):
        actual = self.root / 'other'
        actual.mkdir()
        self.destination.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            installer.install(self.destination, apply=True)


class PackageTests(unittest.TestCase):
    def test_local_reference_links_exist(self):
        for name in installer.PACKAGES:
            root = installer.SOURCE / name
            for path in root.rglob('*.md'):
                for link in re.findall(r'\]\(([^)]+)\)', path.read_text()):
                    if '://' in link or link.startswith('#'):
                        continue
                    self.assertTrue((path.parent / link.split('#')[0]).exists(), f'{path}: {link}')

    def test_reporter_matches_attributed_upstream_revision(self):
        expected = 'af79ca5fa5f06747dbcaa1d40017c8c8e81e0aa11cb8e32b848043893cdb03c7'
        self.assertEqual(hashlib.sha256((SKILL / 'scripts/build-report.mjs').read_bytes()).hexdigest(), expected)


if __name__ == '__main__':
    unittest.main(verbosity=2)
